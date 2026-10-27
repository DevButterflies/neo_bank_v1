"""
Loan lifecycle state machine — Spec §2.

    "Pillar 3 maintains a deterministic, traceable lifecycle for each
    facility. State changes occur only on a confirmed Pillar 2 output
    packet and absent a Pillar 4 veto. Drawdowns freeze on delinquency or
    default. No lifecycle action is taken beyond what the approved terms
    encode."

Design choices, and why:

- The allowed-transitions table below is the *only* place transitions are
  defined. Every action method routes through `_transition`, so a new
  lifecycle action can't accidentally reach a state the Spec table
  doesn't permit.
- Restructuring and Recovery require `human_authorised_for_workout` on
  the packet, not just `officer_confirmed` — Canon §8.6 draws that
  distinction explicitly (restructuring/recovery decisions are owned by
  P2 human credit officers, and P3 "takes no independent decision").
- A veto-frozen facility rejects every transition except the ones that
  the Spec explicitly permits under freeze (recording the freeze itself,
  or closing out per an authorised packet is NOT exempted — the veto is
  "non-overridable by P2/P3").
"""
from __future__ import annotations

from typing import Dict, Set

from bank.pillars.p3.domain.enums import LoanState
from bank.pillars.p3.domain.loan import LoanFacility
from bank.pillars.p3.domain.packet import P2OutputPacket
from bank.pillars.p3.errors import (
    InvalidStateTransitionError,
    UnauthorisedDecisionError,
    UnconfirmedPacketError,
    VetoFrozenError,
)

# Spec §2 state table, expressed as allowed-next-states.
ALLOWED_TRANSITIONS: Dict[LoanState, Set[LoanState]] = {
    LoanState.APPROVED: {LoanState.ACTIVE},
    LoanState.ACTIVE: {LoanState.REPAYING, LoanState.DELINQUENT, LoanState.RESTRUCTURING, LoanState.CLOSED},
    LoanState.REPAYING: {LoanState.REPAYING, LoanState.DELINQUENT, LoanState.RESTRUCTURING, LoanState.CLOSED},
    LoanState.DELINQUENT: {LoanState.REPAYING, LoanState.DEFAULT, LoanState.RESTRUCTURING, LoanState.CLOSED},
    LoanState.DEFAULT: {LoanState.RECOVERY, LoanState.RESTRUCTURING, LoanState.CLOSED},
    LoanState.RESTRUCTURING: {LoanState.ACTIVE, LoanState.CLOSED},
    LoanState.RECOVERY: {LoanState.CLOSED},
    LoanState.CLOSED: set(),
}

# States in which drawdowns must be frozen — Spec §2 ("Drawdowns freeze on
# delinquency or default").
DRAWDOWN_FROZEN_STATES = {LoanState.DELINQUENT, LoanState.DEFAULT}


class LoanLifecycleStateMachine:
    """Stateless-logic wrapper over a LoanFacility. One instance can drive
    any number of facilities; it holds no per-facility state itself."""

    # -- internal ------------------------------------------------------

    def _transition(self, facility: LoanFacility, target: LoanState) -> None:
        if facility.veto_frozen:
            raise VetoFrozenError(
                f"Facility {facility.facility_id} is under an active P4 "
                "veto; the freeze is non-overridable by P2/P3."
            )
        self._require_allowed(facility, target)
        facility.state = target
        facility.touch()

    @staticmethod
    def _require_not_veto_frozen(facility: LoanFacility) -> None:
        if facility.veto_frozen:
            raise VetoFrozenError(
                f"Facility {facility.facility_id} is under an active P4 "
                "veto; the freeze is non-overridable by P2/P3."
            )

    @staticmethod
    def _require_allowed(facility: LoanFacility, target: LoanState) -> None:
        allowed = ALLOWED_TRANSITIONS[facility.state]
        if target not in allowed:
            raise InvalidStateTransitionError(
                f"Facility {facility.facility_id}: {facility.state.value} -> "
                f"{target.value} is not permitted (Spec §2). Allowed: "
                f"{sorted(s.value for s in allowed)}"
            )

    @staticmethod
    def _require_confirmed(packet: P2OutputPacket) -> None:
        if not packet.is_confirmed():
            raise UnconfirmedPacketError(
                f"Packet {packet.packet_id} is not confirmed; P3 shall not "
                "act on a provisional/conditional packet without officer "
                "counter-signature (Canon §8.1)."
            )

    @staticmethod
    def _require_workout_authorised(packet: P2OutputPacket) -> None:
        if not packet.human_authorised_for_workout:
            raise UnauthorisedDecisionError(
                f"Packet {packet.packet_id} carries no human authorisation "
                "for restructuring/recovery; P3 takes no independent "
                "workout decision (Canon §8.6)."
            )

    def is_drawdown_frozen(self, facility: LoanFacility) -> bool:
        return facility.state in DRAWDOWN_FROZEN_STATES or facility.veto_frozen

    # -- lifecycle actions ----------------------------------------------

    def activate(self, facility: LoanFacility, packet: P2OutputPacket) -> None:
        """APPROVED -> ACTIVE on disbursement, per a confirmed packet.

        Check order (Spec §4): veto first, then the valid next state, then
        packet confirmation."""
        self._require_not_veto_frozen(facility)
        self._require_allowed(facility, LoanState.ACTIVE)
        self._require_confirmed(packet)
        self._transition(facility, LoanState.ACTIVE)

    def receive_repayment(self, facility: LoanFacility) -> None:
        """ACTIVE/REPAYING/DELINQUENT -> REPAYING on a scheduled/actual
        repayment. Curing a delinquency is a repayment event too."""
        self._transition(facility, LoanState.REPAYING)

    def mark_delinquent(self, facility: LoanFacility) -> None:
        """-> DELINQUENT on a missed instalment / threshold breach.
        Freezes drawdowns (see is_drawdown_frozen)."""
        self._transition(facility, LoanState.DELINQUENT)

    def mark_default(self, facility: LoanFacility) -> None:
        """DELINQUENT -> DEFAULT on a contractual default trigger."""
        self._transition(facility, LoanState.DEFAULT)

    def restructure(self, facility: LoanFacility, packet: P2OutputPacket) -> None:
        """-> RESTRUCTURING then -> ACTIVE, only on a human-authorised P2
        packet (Canon §8.6). Modelled as a single deterministic action
        because P3 executes the approved terms; it does not sit in an
        intermediate 'restructuring in progress' state of its own
        choosing."""
        self._require_not_veto_frozen(facility)
        self._require_allowed(facility, LoanState.RESTRUCTURING)
        self._require_confirmed(packet)
        self._require_workout_authorised(packet)
        self._transition(facility, LoanState.RESTRUCTURING)
        self._transition(facility, LoanState.ACTIVE)

    def initiate_recovery(self, facility: LoanFacility, packet: P2OutputPacket) -> None:
        """DEFAULT -> RECOVERY, only on a human-authorised recovery
        packet (Canon §8.6: includes the decision to initiate classical
        foreclosure under [G])."""
        self._require_not_veto_frozen(facility)
        self._require_allowed(facility, LoanState.RECOVERY)
        self._require_confirmed(packet)
        self._require_workout_authorised(packet)
        self._transition(facility, LoanState.RECOVERY)

    def close(self, facility: LoanFacility) -> None:
        """-> CLOSED on full repayment / write-off / recovery complete."""
        self._transition(facility, LoanState.CLOSED)
