"""Liquidity Reserve Sizing/Monitor + Concentration Limit Monitor (claude.md §8.6, §8.7).

LIQUIDITY RESERVE (claude.md §8.6): under [G], liquidity risk is ENTIRELY
funding-side (no pledge-side cash demand - a pledger exits by pledge release,
not cash payout). Scope is funding-side/operational outflow schema (SID service,
coupons, disbursement pipeline, foreclosure carrying costs, insurance fees,
guarantee-call settlements pending recoveries). Outputs: LR balance and
minimum-threshold breach flag -> Track 1 veto. The minimum NUMBER is PENDING
(PENDING_LIQUIDITY_MINIMUM); the category schema is built.

CONCENTRATION (claude.md §8.7): four dimensions - single-borrower exposure,
sector, guarantee-pool concentration, funding-source concentration. Pledger
concentration is a GUARANTEE-POOL dimension, NOT funding (pledgers do not fund
loans) - the data model keeps pledgers out of the funding bucket. Percentages
are PENDING (PENDING_CONCENTRATION_LIMITS); the dimension schema is built and
enforcement surfaces the PENDING stop when a limit is unconfigured.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..domain.buffer_account import (
    BufferAccount,
    LiquidityReserveSizingSchema,
    SubAccountId,
)
from ..domain.pending import (
    PENDING_LIQUIDITY_MINIMUM,
    PENDING_CONCENTRATION_LIMITS,
    PendingNotResolvedError,
)


class ConcentrationLimitNotConfigured(PendingNotResolvedError):
    """Concentration-limit percentage(s) not yet resolved (PENDING)."""


@dataclass
class LiquidityMonitor:
    """Sizes the LR against the funding-side outflow schema and flags breaches."""

    schema: LiquidityReserveSizingSchema = field(default_factory=LiquidityReserveSizingSchema)
    # The minimum NUMBER is PENDING; if a governance-approved number is later
    # provided it replaces the PENDING marker (must be > 0).
    minimum_reserve: float | None = None

    def set_minimum_reserve(self, amount: float):
        if amount <= 0:
            raise ValueError("Minimum reserve must be positive")
        self.minimum_reserve = amount

    def lr_balance(self, buffer_account: BufferAccount) -> float:
        return buffer_account.sub_account(SubAccountId.LIQUIDITY_RESERVE).balance

    def required_reserve_appetite(self) -> float:
        """The funding-side outflow category baseline (from the schema)."""
        return self.schema.total_outflow_schema()

    def is_below_minimum(self, buffer_account: BufferAccount) -> bool:
        """Breach flag feeding Track 1 - loud stop if minimum not configured."""
        if self.minimum_reserve is None:
            # No governance number yet: this is a PENDING stop, not a guess.
            raise PendingNotResolvedError(PENDING_LIQUIDITY_MINIMUM)
        return self.lr_balance(buffer_account) < self.minimum_reserve


@dataclass
class ConcentrationMetricsInput:
    single_borrower_share: float = 0.0
    sector_shares: dict = field(default_factory=dict)
    guarantee_pool_single_pledger_share: float = 0.0
    asset_class_shares: dict = field(default_factory=dict)
    funding_source_shares: dict = field(default_factory=dict)
    funding_sources_total: float = 0.0


@dataclass
class ConcentrationMonitor:
    """Tracks four concentration dimensions (schema built; % PENDING)."""

    # Limits, keyed by dimension. When None for a dimension, enforcement
    # surfaces the PENDING stop (never a guess).
    single_borrower_limit: float | None = None
    sector_limit: float | None = None
    guarantee_pool_single_pledger_limit: float | None = None
    asset_class_limit: float | None = None
    funding_source_limit: float | None = None

    def breaches(
        self, m: ConcentrationMetricsInput
    ) -> dict[str, bool]:
        """Return per-dimension breach flags; PENDING limits stop loud."""
        result = {}
        if self.single_borrower_limit is None:
            raise PendingNotResolvedError(PENDING_CONCENTRATION_LIMITS)
        result["single_borrower"] = m.single_borrower_share > self.single_borrower_limit
        result["sector"] = any(
            s > self.sector_limit for s in m.sector_shares.values()
        ) if self.sector_limit is not None else None
        if self.guarantee_pool_single_pledger_limit is None:
            raise PendingNotResolvedError(PENDING_CONCENTRATION_LIMITS)
        result["guarantee_pool_single_pledger"] = (
            m.guarantee_pool_single_pledger_share
            > self.guarantee_pool_single_pledger_limit
        )
        result["asset_class"] = any(
            s > self.asset_class_limit for s in m.asset_class_shares.values()
        ) if self.asset_class_limit is not None else None
        result["funding_source"] = any(
            s > self.funding_source_limit for s in m.funding_source_shares.values()
        ) if self.funding_source_limit is not None else None
        return result

    def any_breach(self, m: ConcentrationMetricsInput) -> bool:
        flags = self.breaches(m)
        return any(v for v in flags.values() if v is True)
