"""Cross-pillar communication adapters (claude.md §9).

There is no existing repository codebase to conform to, so these are plain
in-memory port objects that model how Pillar 4 talks to the other pillars.
They encode the documented interaction pattern faithfully:

  - PILLAR 2 -> P4: risk packets, direct staging signal, required guarantee
                   level; P4 consumes outputs only (no callback to P2).
  - PILLAR 4 -> P2: admissibility POLICY (not case decisions) + the veto STATE
                   that P2 must consult before confirming an output packet
                   (resolution-at-P2; NEVER pushed to Pillar 3).
  - PILLAR 3 -> P4: the typed per-loan events routed to sub-accounts. NO
                   allocation logic returns to Pillar 3.
  - PILLAR 4 -> P3: NOTHING per-loan, ever. The only thing reaching Pillar 3 is
                   the presence/absence of a confirmed P2 packet.
  - PILLAR 5 -> P4: pledge/NFT submissions checked against admissibility POLICY
                   only (not the individual case).
  - ORCHESTRATOR: supplies tier table / perimeter / mode allocation (consumed,
                   never overridden); P4 notifies on every veto freeze.

These ports are the integration surface. If a producer pillar were to be wired
to a real transport later, only this layer changes - not the Pillar 4 core.
"""

from __future__ import annotations

from ..domain.tiers import TierPosition, Tier
from ..domain.events import Pillar3Event, Pillar3EventType
from ..domain.veto import Track
from ..contracts.p2_inbound import (
    Pillar2RiskPacket,
    StagingSignal,
    RequiredGuaranteeLevel,
    CASSFeedRecord,
)
from ..contracts.p5_inbound import PledgeSubmission
from ..contracts.p2_outbound import VetoConsultation, AdmissibilityPolicy


class Pillar2Port:
    """Models Pier 2 -> Pillar 4 + Pillar 4 -> Pillar 2 (resolution point)."""

    def __init__(self, p4):
        self._p4 = p4

    # -- helpers ---------------------------------------------------------------

    def _recompute(self):
        """Event-driven Track-1 recompute after every P4 mutation (claude.md §4.7)."""
        self._p4.recompute_and_evaluate_track1()

    # -- Pillar 2 -> Pillar 4 ----------------------------------------------
    def feed_risk_packet(self, packet: Pillar2RiskPacket):
        """Feed BRR/PD/LGD/EAD/EL (cadence + event-driven) into the capital calc
        and the IFRS9 provisioner. Pillar 4 consumes outputs only."""
        self._p4.capital.register_risk_packet(packet)
        self._p4.ifrs9.register_risk(packet)
        self._recompute()

    def feed_staging_signal(
        self, facility_ref: str, stage: int, packet_ref: str | None = None
    ):
        """Direct IFRS9 staging signal P2 -> EL Pool, BYPASSING Pillar 3."""
        signal = StagingSignal(facility_ref=facility_ref, stage=stage, packet_ref=packet_ref)
        self._p4.ifrs9.on_staging_signal(signal)
        self._recompute()

    def feed_required_guarantee_level(self, required_amount: float, revision_ref: str):
        """P2's required pooled-guarantee level (P4 holds + monitors, never sizes)."""
        self._p4.custody.receive_required_level(
            RequiredGuaranteeLevel(
                required_amount=required_amount, revision_ref=revision_ref
            )
        )
        self._recompute()

    # -- Pillar 4 -> Pillar 2 (resolution-at-P2) ----------------------------
    def consult_veto(self, facility_ref: str | None = None) -> VetoConsultation:
        """P2 consults the P4 veto state before confirming an output packet.

        This is the resolution-at-P2 mechanism: P4 returns confirm/withhold.
        The state is NEVER pushed to Pillar 3.
        """
        from ..part1_core_prudential.veto_engine import VetoResolution

        res = self._p4.veto_engine.consult_before_confirmation(facility_ref)
        t2 = (
            self._p4.veto_engine.state.track2.get(facility_ref)
            if facility_ref is not None
            else None
        )
        return VetoConsultation(
            any_frozen=self._p4.veto_engine.state.any_frozen(),
            track1_frozen=self._p4.veto_engine.state.track1.is_frozen(),
            track1_triggers=tuple(
                t.value for t in self._p4.veto_engine.state.track1.breached_triggers
            ),
            track2_frozen_for_facility=bool(t2 and t2.is_frozen()),
            track2_policy=t2.breached_policy if t2 else None,
        )

    def confirm_packet(self, facility_ref: str) -> bool:
        """The P2 confirmation gate: only confirm if the P4 veto is clear.

        Returns True (packet confirmed) or False (withheld/withdrawn). This is
        the ONLY thing Pillar 3 ever observes - a confirmed or absent packet.

        Facility-aware: a Track 1 global freeze withholds ALL facilities; a
        Track 2 veto is facility-level and withholds only that facility's
        packet (claude.md §8.3), never blocking other, clean facilities.
        """
        cons = self.consult_veto(facility_ref)
        if cons.track1_frozen:
            return False
        if cons.track2_frozen_for_facility:
            return False
        return True


class Pillar3Port:
    """Models Pillar 3 -> Pillar 4 (the ONLY per-loan path INTO Pillar 4)."""

    def __init__(self, p4):
        self._p4 = p4

    def feed_event(self, event: Pillar3Event):
        """Feed a typed Pillar 3 loan-level event into the router.

        P3 performs no allocation; it only records typed events. P4 routes.
        Defaults / guarantee-leg calls are realised LOSS events: they are
        settled through the GuaranteeCallSettlementEngine (draw pool -> EL
        Pool -> ULA Buffer -> funder distribution) instead of a flat, uncapped
        EL Pool debit. On a principal repayment the facility's EAD declines
        (ΔEAD = −0.25 × principal for working-capital lines; dollar-for-dollar
        for amortizing products). The updated packet re-registers in capital +
        IFRS9 and the EL Pool provision re-syncs before the Track-1 recompute.
        """
        if event.event_type == Pillar3EventType.DEFAULT_OR_WRITE_OFF:
            # Loss absorption waterfall. The guarantee leg is the realized loss
            # NET of any collateral leg.
            realized_net = max(0.0, event.amount - event.collateral_leg_amount)
            self._p4.guarantee_call.settle(event.facility_ref, realized_net)
        elif event.event_type == Pillar3EventType.GUARANTEE_CALL_GUARANTEE_LEG:
            # The guarantee-call leg is COMPUTED and SETTLED here; the router
            # only records the call (no double post). Feeding the call into the
            # settlement engine executes the draw/passage/distribution sequence.
            self._p4.guarantee_call.settle(event.facility_ref, event.amount)
        else:
            self._p4.event_router.route(event)
        if (
            event.event_type == Pillar3EventType.SCHEDULED_REPAYMENT
            and event.principal_component > 0
        ):
            updated = self._p4.capital.reduce_ead_for_repayment(
                event.facility_ref, event.principal_component
            )
            if updated is not None:
                self._p4.ifrs9.register_risk(updated)
                self._p4.ifrs9.sync_provision()
        self._p4.recompute_and_evaluate_track1()

    # Pillar 4 -> Pillar 3: DEFINED as absent. There is no outbound per-loan
    # interface to Pillar 3 (claude.md §2.2). The only thing Pillar 3 sees is
    # the P2 packet's presence/absence (see Pillar2Port.confirm_packet).


class Pillar5Port:
    """Models Pillar 5 -> Pillar 4 (pledge/NFT submissions)."""

    def __init__(self, p4):
        self._p4 = p4

    def submit_pledge(self, submission: PledgeSubmission):
        """Submit a pledge; P4 checks its ADMISSIBILITY POLICY only."""
        return self._p4.custody.admit_submission(submission)


class OrchestratorPartner:
    """Models the Orchestrator(s) relationship (claude.md §9, §2)."""

    def __init__(self, notifier=None):
        self._notifier = notifier

    # Orchestrator -> P4: consume authoritative inputs (no carve-out).
    def supply_tier_table(self, p4, table: dict[TierPosition, Tier]):
        p4.tier_service.replace_table_from_orchestrator(table)

    def apply_mode_allocation(self, p4, mode: str):
        # In the current prototype, the mode gate is the single switch.
        return mode

    # P4 -> Orchestrator: notification on every freeze (mandatory, both tracks).
    @property
    def notifications(self):
        if self._notifier is None:
            return []
        return self._notifier.notifications
