"""
The Pillar 2 output packet, as consumed by Pillar 3.

Pillar 3 does not construct these — Pillar 2 does. This module models
only the fields P3 is entitled to read and must record verbatim
(Canon §8.1, Spec §8 audit-record fields). P3 must not infer, derive, or
recompute any field on this packet; it is a pass-through record.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from bank.pillars.p3.domain.enums import CollateralTrack, MaturityStage, P2PacketStatus


@dataclass(frozen=True)
class P2OutputPacket:
    """An approved/provisional/conditional output packet from Pillar 2.

    Attributes mirror exactly what the Canon says P3 records off the
    packet: Model Maturity Stage, BRR-PD grid version, collateral track
    (Canon §8.1), plus the confirmation/authorisation flags P3 must gate
    on before acting (Canon §8.1, §8.6).
    """

    packet_id: str
    facility_id: str
    status: P2PacketStatus
    maturity_stage: MaturityStage
    brr_pd_grid_version: str
    collateral_track: CollateralTrack
    packet_version: str

    # Confirmation gate: Canon §8.1 — origination may not proceed until
    # the credit-officer counter-signature is recorded and the packet
    # status is confirmed.
    officer_confirmed: bool = False
    officer_id: Optional[str] = None

    # Human authorisation for restructuring/recovery — Canon §8.6. This is
    # deliberately a *separate* flag from officer_confirmed: origination
    # confirmation and a restructuring/recovery authorisation are not the
    # same act and must not be conflated.
    human_authorised_for_workout: bool = False

    issued_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def is_confirmed(self) -> bool:
        """A packet is 'confirmed' for origination purposes only when its
        status is not left provisional/conditional without sign-off."""
        if self.status is P2PacketStatus.APPROVED:
            return True
        # PROVISIONAL / CONDITIONAL require the officer counter-signature.
        return self.officer_confirmed and self.officer_id is not None
