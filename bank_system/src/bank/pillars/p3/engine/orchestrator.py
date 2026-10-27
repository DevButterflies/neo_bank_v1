"""
Pillar3Orchestrator — the single façade that wires the engine together
for a full loan lifecycle, and the only place that writes AuditRecords.

Nothing in this class computes an allocation, a haircut, a risk rating,
or a prudential threshold. It sequences: gate -> state machine -> posting
-> audit. Every public method corresponds to a named action in Spec §2's
state table or Build Handoff §4's posting table, and every one of them
ends by appending exactly one AuditRecord (Spec §8).
"""
from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from typing import Optional

from bank.pillars.p3.audit.trail import AuditTrail
from bank.pillars.p3.core_banking.interface import CoreBankingClient
from bank.pillars.p3.domain.collateral import CollateralObject
from bank.pillars.p3.domain.enums import LoanState, PostingEventType
from bank.pillars.p3.domain.events import AuditRecord, PostingEvent
from bank.pillars.p3.domain.loan import LoanFacility
from bank.pillars.p3.domain.memos import (
    MEMO_DEFAULT_MARKER,
    MEMO_DISBURSEMENT,
    MEMO_RECOVERY,
    MEMO_SCHEDULED_INTEREST,
    MEMO_SCHEDULED_PRINCIPAL,
    MEMO_WRITE_OFF,
)
from bank.pillars.p3.domain.packet import P2OutputPacket
from bank.pillars.p3.engine.collateral_service import CollateralService
from bank.pillars.p3.engine.posting_service import PostingService
from bank.pillars.p3.engine.state_machine import LoanLifecycleStateMachine
from bank.pillars.p3.errors import RepaymentExceedsOutstandingError, WriteOffExceedsOutstandingError
from bank.pillars.p3.interfaces.p2_gate import P2Gate
from bank.pillars.p3.interfaces.p4_router import P4VetoRouter
from bank.pillars.p3.interfaces.p5_gate import P5Gate

# Float slack allowed when comparing "repaid + this" against "disbursed".
_REPAYMENT_TOLERANCE = 0.005


class Pillar3Orchestrator:
    def __init__(self, core_banking: CoreBankingClient) -> None:
        self.state_machine = LoanLifecycleStateMachine()
        self.posting_service = PostingService(core_banking)
        self.collateral_service = CollateralService()
        self.p2_gate = P2Gate()
        self.p4_router = P4VetoRouter()
        self.p5_gate = P5Gate()
        self.audit_trail = AuditTrail()
        self._facilities: dict[str, LoanFacility] = {}

    # -- facility registry ------------------------------------------------

    def get_or_create_facility(self, facility_id: str) -> LoanFacility:
        if facility_id not in self._facilities:
            self._facilities[facility_id] = LoanFacility(facility_id=facility_id)
        return self._facilities[facility_id]

    def get_facility(self, facility_id: str) -> Optional[LoanFacility]:
        """Read-only facility lookup (never creates). Used by the P1 simulator
        to make retried lifecycle steps idempotent against already-committed
        transitions."""
        return self._facilities.get(facility_id)

    # -- audit helper -------------------------------------------------------

    def _record_audit(
        self,
        facility: LoanFacility,
        packet: P2OutputPacket,
        event_type: str,
        posting_event: Optional[PostingEvent] = None,
        collateral: Optional[CollateralObject] = None,
        actor: str = "SYSTEM",
    ) -> AuditRecord:
        veto_status = self.p4_router.veto_status(facility)
        veto_str = "; ".join(f"{k.value}:{v}" for k, v in veto_status.items())

        record = AuditRecord(
            record_id=f"AUD-{uuid.uuid4().hex[:12]}",
            facility_id=facility.facility_id,
            event_type=event_type,
            timestamp=datetime.now(timezone.utc),
            actor_reference=actor,
            p2_packet_version=packet.packet_version,
            maturity_stage=packet.maturity_stage,
            brr_pd_grid_version=packet.brr_pd_grid_version,
            collateral_track=collateral.track if collateral else None,
            p4_veto_status=veto_str,
            posting_routing_flag=(
                posting_event.event_type.value if posting_event else None
            ),
            core_banking_confirmed=posting_event is not None,
            resulting_state=facility.state,
            collateral_reference=collateral.collateral_id if collateral else None,
        )
        self.audit_trail.append(record)
        return record

    # -- lifecycle actions (Spec §2), each producing exactly one audit record

    def originate(self, packet: P2OutputPacket, production_auto_approval=None) -> LoanFacility:
        self.p2_gate.receive_packet(packet)
        confirmed_packet = self.p2_gate.authorize_origination(
            packet.packet_id, production_auto_approval
        )
        facility = self.get_or_create_facility(packet.facility_id)
        # APPROVED is the initial state already; origination just confirms
        # the packet is on file before disbursement can proceed.
        facility.origination_packet_id = confirmed_packet.packet_id
        self._record_audit(facility, confirmed_packet, "ORIGINATION_RECORDED")
        return facility

    def disburse(self, facility_id: str, packet: P2OutputPacket, amount: float, currency: str) -> PostingEvent:
        facility = self.get_or_create_facility(facility_id)
        self.p4_router.assert_not_frozen(facility)
        self.state_machine.activate(facility, packet)
        event = self.posting_service.capture_and_post(
            facility_id, PostingEventType.PRINCIPAL_MOVEMENT, amount, currency, packet.packet_id,
            memo=MEMO_DISBURSEMENT,
        )
        self._record_audit(facility, packet, "DISBURSEMENT", posting_event=event)
        return event

    def pledge_collateral(self, facility_id: str, packet: P2OutputPacket, external_reference: Optional[str] = None) -> CollateralObject:
        facility = self.get_or_create_facility(facility_id)
        collateral = self.collateral_service.record_msme_pledged_collateral(
            facility, packet, external_reference
        )
        self._record_audit(facility, packet, "COLLATERAL_PLEDGED", collateral=collateral)
        return collateral

    def _principal_totals(self, facility_id: str) -> tuple[float, float]:
        """``(disbursed, repaid)`` for one facility, from posted events only.

        Core banking has no balance field of its own to consult, so the
        outstanding principal is reconstructed from the ledger P3 itself
        posted — the same events the bilan aggregates.
        """
        disbursed = 0.0
        repaid = 0.0
        for event in self.posting_service.posted_events():
            if event.facility_id != facility_id:
                continue
            if event.event_type is not PostingEventType.PRINCIPAL_MOVEMENT:
                continue
            if event.memo == MEMO_DISBURSEMENT:
                disbursed += event.amount
            else:
                repaid += event.amount
        return round(disbursed, 2), round(repaid, 2)

    def _assert_repayable(
        self, facility_id: str, principal_amount: float, interest_amount: float
    ) -> None:
        """Reject any repayment that would drive the outstanding balance below
        zero (docs/CHANGELOG_bilan.md, B5), and any amount a ledger cannot represent.

        ``nan < 0`` and ``nan > cap`` are both ``False``, so a NaN principal
        would otherwise sail straight through the balance check — interest is
        validated here for the same reason, before the state machine moves
        (bug_bilan_fix_round_2.md, R2).

        A facility with no disbursement on record is skipped rather than
        rejected: the cap has nothing to measure against yet.
        """
        if not math.isfinite(principal_amount) or principal_amount < 0:
            raise ValueError(
                f"{facility_id}: principal_amount must be a finite, "
                f"non-negative number (got {principal_amount!r})"
            )
        if not math.isfinite(interest_amount) or interest_amount < 0:
            raise ValueError(
                f"{facility_id}: interest_amount must be a finite, "
                f"non-negative number (got {interest_amount!r})"
            )
        disbursed, repaid = self._principal_totals(facility_id)
        if disbursed <= 0.0:
            return
        if repaid + principal_amount > disbursed + _REPAYMENT_TOLERANCE:
            raise RepaymentExceedsOutstandingError(
                f"{facility_id}: repaid {repaid:.2f} + {principal_amount:.2f} "
                f"would exceed the {disbursed:.2f} disbursed by "
                f"{repaid + principal_amount - disbursed:.2f}"
            )

    def _assert_writable(self, facility_id: str, loss_amount: float) -> None:
        """Reject any write-off that could not be true (``bug_bilan_fix_round_2.md``, R1).

        The amount has to be a real, non-negative number, and it can never
        exceed the principal still outstanding: writing off more than was
        ever lent would push loss onto the passif without a matching debit.
        A facility with no disbursement on record is skipped rather than
        rejected — there is nothing to measure against yet.
        """
        if not math.isfinite(loss_amount) or loss_amount < 0:
            raise ValueError(
                f"{facility_id}: loss_amount must be a finite, non-negative "
                f"number (got {loss_amount!r})"
            )
        disbursed, repaid = self._principal_totals(facility_id)
        if disbursed <= 0.0:
            return
        outstanding = round(disbursed - repaid, 2)
        if loss_amount > outstanding + _REPAYMENT_TOLERANCE:
            raise WriteOffExceedsOutstandingError(
                f"{facility_id}: write-off {loss_amount:.2f} exceeds the "
                f"{outstanding:.2f} still outstanding by "
                f"{loss_amount - outstanding:.2f}"
            )

    def record_repayment(
        self,
        facility_id: str,
        packet: P2OutputPacket,
        interest_amount: float,
        principal_amount: float,
        currency: str,
    ) -> tuple[PostingEvent, PostingEvent]:
        facility = self.get_or_create_facility(facility_id)
        self.p4_router.assert_not_frozen(facility)
        self._assert_repayable(facility_id, principal_amount, interest_amount)
        self.state_machine.receive_repayment(facility)
        income_event = self.posting_service.capture_and_post(
            facility_id, PostingEventType.LOAN_INCOME, interest_amount, currency, packet.packet_id,
            memo=MEMO_SCHEDULED_INTEREST,
        )
        principal_event = self.posting_service.capture_and_post(
            facility_id, PostingEventType.PRINCIPAL_MOVEMENT, principal_amount, currency, packet.packet_id,
            memo=MEMO_SCHEDULED_PRINCIPAL,
        )
        self._record_audit(facility, packet, "REPAYMENT", posting_event=income_event)
        self._record_audit(facility, packet, "REPAYMENT", posting_event=principal_event)
        return income_event, principal_event

    def mark_delinquent(self, facility_id: str, packet: P2OutputPacket) -> None:
        facility = self.get_or_create_facility(facility_id)
        self.state_machine.mark_delinquent(facility)
        self._record_audit(facility, packet, "DELINQUENCY")

    def _has_write_off(self, facility_id: str) -> bool:
        return any(
            event.facility_id == facility_id
            and event.event_type is PostingEventType.LOSS_RECOVERY
            and event.memo == MEMO_WRITE_OFF
            for event in self.posting_service.posted_events()
        )

    def mark_default(
        self,
        facility_id: str,
        packet: P2OutputPacket,
        loss_amount: float = 0.0,
        currency: str = "USD",
    ) -> PostingEvent:
        """Book a default: the zero-amount marker, plus — optionally — the
        write-off of whatever principal is still outstanding.

        ``loss_amount`` defaults to ``0.0`` so every existing caller keeps
        posting exactly the marker it always did. The P1 simulator passes the
        real outstanding balance, so the residual principal leaves the ledger
        instead of sitting there forever (docs/CHANGELOG_bilan.md, B2).

        Idempotent: a retried default never writes a second ``write-off``
        event for the same facility.

        The amount is validated *first*, so a rejected write-off leaves the
        ledger and the state machine untouched — no marker, no posting, no
        partial default (``bug_bilan_fix_round_2.md``, R1).
        """
        self._assert_writable(facility_id, loss_amount)
        facility = self.get_or_create_facility(facility_id)
        self.state_machine.mark_default(facility)
        marker = self.posting_service.capture_and_post(
            facility_id, PostingEventType.LOSS_RECOVERY, 0.0, "N/A", packet.packet_id,
            memo=MEMO_DEFAULT_MARKER,
        )
        self._record_audit(facility, packet, "DEFAULT", posting_event=marker)

        if loss_amount > 0.0 and not self._has_write_off(facility_id):
            write_off = self.posting_service.capture_and_post(
                facility_id, PostingEventType.LOSS_RECOVERY, float(loss_amount), currency,
                packet.packet_id,
                memo=MEMO_WRITE_OFF,
            )
            self._record_audit(facility, packet, "WRITE_OFF", posting_event=write_off)
        return marker

    def restructure(self, facility_id: str, packet: P2OutputPacket) -> None:
        facility = self.get_or_create_facility(facility_id)
        self.state_machine.restructure(facility, packet)
        self._record_audit(facility, packet, "RESTRUCTURING_EXECUTED", actor=packet.officer_id or "SYSTEM")

    def initiate_recovery(self, facility_id: str, packet: P2OutputPacket, recovered_amount: float, currency: str) -> PostingEvent:
        facility = self.get_or_create_facility(facility_id)
        self.state_machine.initiate_recovery(facility, packet)
        recovery_event = self.posting_service.capture_and_post(
            facility_id, PostingEventType.LOSS_RECOVERY, recovered_amount, currency, packet.packet_id,
            memo=MEMO_RECOVERY,
        )
        self._record_audit(facility, packet, "RECOVERY_EXECUTED", posting_event=recovery_event,
                            actor=packet.officer_id or "SYSTEM")
        return recovery_event

    def close(self, facility_id: str, packet: P2OutputPacket) -> None:
        facility = self.get_or_create_facility(facility_id)
        self.state_machine.close(facility)
        self._record_audit(facility, packet, "CLOSURE")
