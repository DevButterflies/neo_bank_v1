"""
Collateral objects — three-track model (Spec §4) and the two structurally
distinct collateral objects (Spec §4.1 / Canon §5.2).

P3 records confirmed collateral objects only; it performs NO admissibility
validation and NO haircut computation (that is P4→P2, and Track 2/3
haircut governance is a strict PENDING item — see governance/pending.py).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from bank.pillars.p3.domain.enums import CollateralTrack, ModelFlag


class CollateralObjectKind(str, Enum):
    """The two structurally distinct collateral objects — Canon §5.2 /
    Spec §4.1. P3 must never conflate these."""

    MSME_PLEDGED = "MSME_PLEDGED"              # facility-specific, non-pooled
    NEO_BANK_POOLED_GUARANTEE = "NEO_BANK_POOLED_GUARANTEE"  # portfolio-level, P4-held


@dataclass(frozen=True)
class CollateralObject:
    """A single collateral object recorded against a facility.

    Recording a collateral object requires a validated P2 packet
    (`p2_packet_id`) — this is enforced by the collateral service, not by
    this dataclass, but the field is mandatory here so a collateral
    object can never exist without a traceable source packet.
    """

    collateral_id: str
    facility_id: str
    kind: CollateralObjectKind
    track: CollateralTrack
    model_flag: ModelFlag
    p2_packet_id: str  # the validated packet that authorised this object
    recorded_at: datetime = None  # set by the service at creation time
    external_reference: Optional[str] = None  # e.g. NFT ID, escrow ref

    def __post_init__(self) -> None:
        if self.recorded_at is None:
            object.__setattr__(self, "recorded_at", datetime.now(timezone.utc))

        if self.track is CollateralTrack.TRACK_3_STABLECOIN and self.model_flag is not ModelFlag.STABLECOIN:
            raise ValueError(
                "Track 3 (stablecoin) is [S]-only per Spec §4 — cannot be "
                "recorded under the [G] model flag."
            )
