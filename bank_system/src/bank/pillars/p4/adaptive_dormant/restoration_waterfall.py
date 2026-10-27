"""Reverse Restoration Waterfall (claude.md §13, Workflow E).

Post-stress restoration, run in REVERSE order of absorption. Because ABSF
absorbs across Tier D / Tier B-Fees / Tier C in a documented order, restoration
returns in the reverse order, restoring each tier before the next.

Dormant in Conventional Mode; the reverse-absorption ORDER is PENDING
(PENDING_CASS_FEED_SPEC). The structure is complete; the specific order of
restoration is a named stop.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..domain.pending import PENDING_CASS_FEED_SPEC, PendingNotResolvedError
from ..mode_gate.mode_gate import ModeGateService


class RestorationWaterfall:
    """Restores tiers in reverse absorption order after sustained recovery."""

    def __init__(self, mode_gate: ModeGateService, restore_order: tuple[str, ...] | None = None):
        self._mode = mode_gate
        # Reverse absorption order; None => order itself is PENDING.
        self.restore_order = restore_order
        self._restored: dict[str, float] = {}

    def _require_ready(self):
        self._mode.require_adaptive()
        if not self.restore_order:
            raise PendingNotResolvedError(PENDING_CASS_FEED_SPEC)

    def restore(self, recoverable_capacity: float) -> dict[str, float]:
        """Restore each tier in reverse order up to the given capacity."""
        self._require_ready()
        remaining = recoverable_capacity
        result: dict[str, float] = {}
        for tier in self.restore_order:
            taken = min(remaining, 0.0 if remaining <= 0 else remaining)
            result[tier] = taken
            self._restored[tier] = self._restored.get(tier, 0.0) + taken
            remaining -= taken
            if remaining <= 0:
                break
        return result

    @property
    def restoration_detail(self) -> dict[str, float]:
        return dict(self._restored)
