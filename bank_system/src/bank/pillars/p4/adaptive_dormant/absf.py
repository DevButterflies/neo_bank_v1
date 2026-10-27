"""Adaptive Burden-Sharing Framework (claude.md §13, Workflow E).

ABSF operates on EXACTLY Tier D / Tier B-Fees / Tier C - never Senior Debt,
never Tier A (both explicitly excluded from ABSF participation).

On a CASS stress zone, ABSF applies the zone's participation weights across
those three tiers to share the burden of a crystallized stress event. The
weights-by-zone are PENDING (PENDING_CASS_FEED_SPEC / Part III methodology) -
the framework structure is complete, the specific weights are named stops.

Also dormant in Conventional Mode: Tier B-Fees interruption/resumption
mechanics run contractually (Stage 1) but ABSF-level participation is gated.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .cass_engine import CASSZone, CassEngine
from ..domain.pending import PENDING_CASS_FEED_SPEC, PendingNotResolvedError


@dataclass
class AbsfWeights:
    """ABSF participation weights per zone for Tier D / Tier B-Fees / Tier C.

    None => unresolvable until the CASS/ABSF methodology is ratified.
    """

    tier_d: dict[str, float] | None = None
    tier_b_fees: dict[str, float] | None = None
    tier_c: dict[str, float] | None = None

    @property
    def resolved(self) -> bool:
        return None not in (self.tier_d, self.tier_b_fees, self.tier_c)


class AbsfFramework:
    """Applies ABSF participation weights across Tier D / Tier B-Fees / Tier C."""

    def __init__(self, cass_engine: CassEngine, weights: AbsfWeights | None = None):
        self._cass = cass_engine
        self.weights = weights or AbsfWeights()
        self.participating_tiers = ("Tier D", "Tier B-Fees", "Tier C")
        self._application_history: list[dict] = []

    def _require_resolved(self):
        # ABSF implicitly requires Adaptive Mode (its CASS trigger must run).
        if not self.weights.resolved:
            raise PendingNotResolvedError(PENDING_CASS_FEED_SPEC)

    def participation_weights_for(self, zone: CASSZone) -> dict[str, float]:
        self._require_resolved()
        return {
            "Tier D": self.weights.tier_d[zone.value],
            "Tier B-Fees": self.weights.tier_b_fees[zone.value],
            "Tier C": self.weights.tier_c[zone.value],
        }

    def apply_burden(self, zone: CASSZone, stress_amount: float) -> dict[str, float]:
        """Split a stress amount across the three participating tiers by zone weight.

        Senior Debt and Tier A are NEVER touched (structurally excluded).
        """
        self._require_resolved()
        if stress_amount < 0:
            raise ValueError("stress_amount must be non-negative")
        weights = self.participation_weights_for(zone)
        total_w = sum(weights.values())
        shares = {t: stress_amount * (w / total_w) for t, w in weights.items()}
        self._application_history.append({"zone": zone.value, "shares": dict(shares)})
        return shares
