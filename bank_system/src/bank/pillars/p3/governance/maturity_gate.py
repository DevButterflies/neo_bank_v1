"""
Model Maturity Stage gate — Spec §1, Build Handoff §5 ("Binding gate — do
not build auto-origination for sandbox").

    DESIGN:     no live loans; [G] built, [S] stubbed.
    SANDBOX:    live pilot loans; human credit-officer gate mandatory at
                every decision zone; NO auto-origination path may exist.
    PRODUCTION: conditional auto-consumption permitted, but only after
                explicit P4 approval + Orchestrator notification.

This module is the single choke point origination must pass through. It
does not merely check a flag — DESIGN and SANDBOX literally cannot reach
an auto-origination code path through this gate, because the gate raises
before origination proceeds unless an officer confirmation or an
explicit, separately-recorded P4 production approval is present.
"""
from __future__ import annotations

from dataclasses import dataclass

from bank.pillars.p3.domain.enums import MaturityStage
from bank.pillars.p3.domain.packet import P2OutputPacket
from bank.pillars.p3.errors import AutoOriginationNotPermittedError, UnconfirmedPacketError


@dataclass(frozen=True)
class ProductionAutoApproval:
    """Explicit P4 approval + Orchestrator notification required before
    PRODUCTION auto-consumption is permitted (Build Handoff §5)."""

    approved_by_p4: bool
    orchestrator_notified: bool

    def is_valid(self) -> bool:
        return self.approved_by_p4 and self.orchestrator_notified


def check_origination_gate(
    packet: P2OutputPacket,
    production_auto_approval: ProductionAutoApproval | None = None,
) -> None:
    """Raise if origination on this packet is not permitted at its
    Maturity Stage. Returns normally (no return value) if permitted.
    """
    # Officer-confirmed packets are always fine to originate on, at any
    # stage — the human gate has already been satisfied.
    if packet.is_confirmed():
        return

    # From here on, packet is NOT officer-confirmed: this would only be
    # reachable via conditional auto-approve.
    if packet.maturity_stage in (MaturityStage.DESIGN, MaturityStage.SANDBOX):
        raise AutoOriginationNotPermittedError(
            f"Packet {packet.packet_id} is unconfirmed and Maturity Stage "
            f"is {packet.maturity_stage.value}. Straight-through "
            "auto-origination must not exist as a SANDBOX/DESIGN "
            "capability (Build Handoff §5)."
        )

    if packet.maturity_stage is MaturityStage.PRODUCTION:
        if production_auto_approval is None or not production_auto_approval.is_valid():
            raise AutoOriginationNotPermittedError(
                f"Packet {packet.packet_id} is unconfirmed at PRODUCTION "
                "but no valid explicit P4 approval + Orchestrator "
                "notification was supplied (Build Handoff §5)."
            )
        return  # PRODUCTION + valid approval: auto-consumption permitted

    # Defensive: unreachable with current enum, but fail closed.
    raise UnconfirmedPacketError(
        f"Packet {packet.packet_id} is unconfirmed and no gate rule "
        f"covers Maturity Stage {packet.maturity_stage!r}."
    )
