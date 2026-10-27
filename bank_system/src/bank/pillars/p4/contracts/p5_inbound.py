"""Pillar 5 -> Pillar 4 inbound contracts (pledge / NFT submissions).

claude.md §5.4, §9: Pillar 5 submits admissible pledge guarantees and NFT
collateral records (the submitted pool-layer objects). Pillar 4 reviews against
its ADMISSIBILITY POLICY only - eligible asset types, haircuts, concentration
limits - and admits or rejects at POLICY level. Pillar 4 does NOT enter the
individual case; Pillar 2 confirms admissibility in the individual case and
recalculates LGD/EL.

Stage 1 is Track 1 (Classical) collateral only - no NFT (Track 2) or stablecoin
(Track 3, [S]-only) yet. The three-track haircut governance is PENDING
(PENDING_THREE_TRACK_HAIRCUT, Track 2/3 only; does not block Stage 1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone

from ..domain.guarantee_pool import Pillar5AdmittedCollateral
from ..domain.tiers import TierPosition


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SubmissionDisposition(str, Enum):
    ADMITTED = "admitted"
    REJECTED = "rejected"


@dataclass(frozen=True)
class PledgeSubmission:
    """A Pillar 5 submission of a pooled Layer (Tier A / Tier B) pledge position.

    The eligible_types/haircut/concentration checks are made against Pillar 4's
    ADMISSIBILITY POLICY. The pledge carries its tier; only Tier A / Tier B
    positions enter the pool (funding-vs-collateral boundary).
    """

    submission_ref: str
    pledger_id: str
    tier: TierPosition
    amount: float
    asset_class: str
    submitted_at: datetime = field(default_factory=_utcnow)

    def __post_init__(self):
        if self.tier not in (TierPosition.TIER_A, TierPosition.TIER_B):
            raise ValueError(
                f"Pledge submission tier must be Tier A or Tier B, got "
                f"{self.tier.value}. Loan funding is not a guarantee position."
            )


@dataclass(frozen=True)
class AdmittedSubmitResult:
    """Outcome of Pillar 4's policy-level admissibility gate for a submission."""

    submission_ref: str
    disposition: SubmissionDisposition
    reason: str
    policy_version: str | None = None
