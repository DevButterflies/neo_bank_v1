"""Guarantee pool, pledge positions, and the Two-Guarantee-Layer Rule.

claude.md §3, §5.4, §8.12: the guarantee pool is the aggregate Tier A + Tier B
contingent-cash-equivalent positions pooled-pledged as collateral. Those are
guarantees RECEIVED by the neo-bank. They are COLLATERAL, not funding.

The Two-Guarantee-Layer Rule (claude.md §3, §14) is enforced STRUCTURALLY here
by making MSME-pledged collateral a DISTINCT type from the pooled guarantee -
not a shared type with a flag:
  - :class:`Pillar5AdmittedCollateral` - the per-facility MSME-pledged asset
    (feeds per-facility LGD; never pooled).
  - :class:`PledgePosition` - a Tier A / Tier B pledged guarantee position that
    enters the POOL.
These are different classes; conflation is unrepresentable.

Pillar 4 HOLDS the pool and monitors adequacy against Pillar 2's REQUIRED
level; Pillar 4 NEVER re-sizes that requirement (claude.md §5.4/§5.2, §8.12).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .tiers import TierPosition


class PledgeReleaseState(str, Enum):
    NONE = "none"
    REQUESTED = "requested"
    ADEQUACY_MANAGED = "adequacy_managed"
    RELEASED = "released"


class PoolAdequacyStatus(str, Enum):
    ADEQUATE = "adequate"
    SHORTFALL = "shortfall"


@dataclass
class Pillar5AdmittedCollateral:
    """MSME-pledged, facility-specific collateral (per-facility LGD).

    DISTINCT type from PledgePosition (Two-Guarantee-Layer Rule). This is the
    borrower's OWN pledge, recorded in the loan execution record and used to
    realise the COLLATERAL leg of default by classical foreclosure.
    """

    collateral_ref: str
    facility_ref: str
    asset_class: str
    admitted_value: float  # haircut-adjusted, as confirmed by Pillar 2
    track: int = 1  # Stage 1 is Track 1 (Classical) collateral only


@dataclass
class PledgePosition:
    """A Tier A / Tier B pledge that enters the pooled guarantee (POOL layer).

    Distinct type from Pillar5AdmittedCollateral. Exists per pledger; carries
    its release state machine.
    """

    pledge_ref: str
    tier: TierPosition  # Tier A or Tier B only
    amount: float  # contingent-cash-equivalent value post-haircut
    pledge_term: float  # units TBD (PENDING_PLEDGE_TERM); kept as duration
    release_state: PledgeReleaseState = PledgeReleaseState.NONE
    notice_period_start: object | None = None
    penalty_applicable: dict | None = None  # populated on pre-term exception

    def validated(self):
        if self.tier not in (TierPosition.TIER_A, TierPosition.TIER_B):
            raise ValueError(f"Pledge tier must be Tier A or Tier B, got {self.tier}")
        return self


@dataclass
class GuaranteePool:
    """Portfolio-level guarantee pool held by Pillar 4 (Part II).

    Composition = aggregate Tier A + Tier B positions. Adequacy is monitored by
    continuous comparison of guarantees RECEIVED against Pillar 2's REQUIRED
    level. Pillar 4 NEVER re-sizes the requirement; it only compares.
    """

    positions: list[PledgePosition] = field(default_factory=list)

    # Required level as supplied by Pillar 2 (received, versioned/timestamped).
    required_level: float = 0.0
    required_level_revision: str | None = None

    # Aggregate given/received guarantee books (the macro isomorphism,
    # claude.md §5.4/§5.6).
    received_guarantee_book: float = 0.0
    given_guarantee_book: float = 0.0

    def received_received_value(self) -> float:
        """Sum of received Tier A + Tier B positions (post-haircut)."""
        return sum(p.amount for p in self.positions)

    def adequacy_status(self) -> PoolAdequacyStatus:
        received = self.received_received_value()
        if self.required_level <= 0:
            # No required level supplied yet: cannot judge shortfall; treated as
            # adequate with zero requirement. (Require output to be set by P2.)
            return PoolAdequacyStatus.ADEQUATE
        if received >= self.required_level - 1e-9:
            return PoolAdequacyStatus.ADEQUATE
        return PoolAdequacyStatus.SHORTFALL

    def add_position(self, position: PledgePosition):
        position.validated()
        self.positions.append(position)

    def remove_position(self, pledge_ref: str) -> PledgePosition:
        idx = next(
            (i for i, p in enumerate(self.positions) if p.pledge_ref == pledge_ref),
            None,
        )
        if idx is None:
            raise KeyError(f"No pledge position {pledge_ref}")
        removed = self.positions.pop(idx)
        return removed


@dataclass
class ConcentrationMetrics:
    """Guarantee-pool concentration metrics (claude.md §5.4/§5.5, §8.12).

    Pledger concentration is a GUARANTEE-POOL dimension, NOT a funding dimension
    (pledgers do not fund loans) - claude.md §5.4/§5.5, §8.7.
    """

    single_pledger_share: float = 0.0  # share of pool from one pledger (0..1]
    asset_class_concentration: dict = field(default_factory=dict)
    # PENDING concentration limit percentages (claude.md §17).
    # Limits live in policy/config, not here.
