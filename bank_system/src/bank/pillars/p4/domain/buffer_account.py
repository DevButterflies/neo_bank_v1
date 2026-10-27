"""Buffer account and its four sub-accounts (claude.md §5.4, §8.9, §8.10).

The buffer account is the central aggregation/distribution mechanism for all
loan-level economic events at portfolio level - the macro side of the
micro/macro cut (claude.md §5.3/§1.1). It is SEPARATE from the core banking
current-account ledger; it is a prudential aggregation structure (claude.md
§5.3/§1.2).

Four sub-accounts (claude.md §5.4 table):
  EL Pool   - IFRS 9 ECL provisions; funded by risk premium, up to 2% Budgeted
              Loss; receives the direct P2 staging signal.
  ULA Buffer- unexpected-loss-absorption capacity beyond Budgeted Loss;
              professional capital + retained margin.
  LR        - global fiat liquidity; FUNDING-SIDE-ONLY buffer.
  RP Pool   - risk-premium income stream; funds EL Pool; Tier B-Fees basis.

Each sub-account declares a DORMANT CASS-component binding socket (claude.md
§5.4/§2.5): the ledger is dimensioned for Stage-2 CASS/ABSF consumption without
activating it. "Sockets declared; none armed."
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from .pending import (
    PendingItem,
    PENDING_LIQUIDITY_MINIMUM,
    pending_keys,
)
from .events import IntraP4Event, IntraP4EventType


class SubAccountId(str, Enum):
    EL_POOL = "el_pool"
    ULA_BUFFER = "ula_buffer"
    LIQUIDITY_RESERVE = "liquidity_reserve"
    RP_POOL = "rp_pool"


class CassComponent(str, Enum):
    """Dormant Stage-2 CASS-component binding points (claude.md §5.4/§2.5)."""

    CASS_SOLVENCY_STRESS = "cass_solvency_stress"
    ABSF_DRAWDOWN_REPLENISHMENT = "absf_drawdown_replenishment"
    CASS_LIQUIDITY_STRESS = "cass_liquidity_stress"
    TIER_B_FEES_INTERRUPTION = "tier_b_fees_interruption_resumption"


# Map each sub-account to its dormant Stage-2 CASS socket (claude.md §5.4 §2.5).
SUB_ACCOUNT_CASS_SOCKET: dict[SubAccountId, CassComponent] = {
    SubAccountId.EL_POOL: CassComponent.CASS_SOLVENCY_STRESS,
    SubAccountId.ULA_BUFFER: CassComponent.ABSF_DRAWDOWN_REPLENISHMENT,
    SubAccountId.LIQUIDITY_RESERVE: CassComponent.CASS_LIQUIDITY_STRESS,
    SubAccountId.RP_POOL: CassComponent.TIER_B_FEES_INTERRUPTION,
}


@dataclass
class SubAccount:
    """One of the four separately-balanced sub-accounts under a buffer parent."""

    _id: SubAccountId
    balance: float = 0.0
    # Tier attribution carried on every posting - reserved for Stage-2 ABSF
    # weight computation (claude.md §5.4 "Reserved (dormant) Stage-2 sockets").
    # Map of tier_position.value -> posted amount currently sitting here.
    tier_attribution: dict = field(default_factory=dict)
    # Reserved routing fields for Stage-2 CASS/ABSF consumption; unpopulated.
    stage2_socket_active: bool = False

    @property
    def id(self) -> SubAccountId:
        return self._id

    @property
    def cass_socket(self) -> CassComponent:
        return SUB_ACCOUNT_CASS_SOCKET[self._id]

    def _apply_tier(self, amount: float, tier_position: str):
        previous = self.tier_attribution.get(tier_position, 0.0)
        updated = previous + amount
        if abs(updated) < 1e-9:
            self.tier_attribution.pop(tier_position, None)
        else:
            self.tier_attribution[tier_position] = updated

    def credit(self, amount: float, tier_position: str | None = None):
        """Credit this sub-account, optionally carrying tier attribution."""
        self.balance += amount
        if tier_position is not None:
            self._apply_tier(amount, tier_position)

    def debit(self, amount: float, tier_position: str | None = None):
        """Debit this sub-account, optionally carrying tier attribution.

        Sub-accounts may legitimately go negative in the EL/ULA flow (loss
        absorption and provision utilisation); the LR enforces its minimum
        threshold at the monitor level, not here.
        """
        self.balance -= amount
        if tier_position is not None:
            self._apply_tier(-amount, tier_position)


@dataclass
class BufferAccount:
    """BufferAccount parent holding four separately-balanced sub-accounts.

    Owned by Part II; Part I only reads balances (claude.md §6 "Part II owns
    the accounts").
    """

    el_pool: SubAccount = field(default_factory=lambda: SubAccount(SubAccountId.EL_POOL))
    ula_buffer: SubAccount = field(
        default_factory=lambda: SubAccount(SubAccountId.ULA_BUFFER)
    )
    liquidity_reserve: SubAccount = field(
        default_factory=lambda: SubAccount(SubAccountId.LIQUIDITY_RESERVE)
    )
    rp_pool: SubAccount = field(
        default_factory=lambda: SubAccount(SubAccountId.RP_POOL)
    )

    def sub_account(self, sid: SubAccountId) -> SubAccount:
        return {
            SubAccountId.EL_POOL: self.el_pool,
            SubAccountId.ULA_BUFFER: self.ula_buffer,
            SubAccountId.LIQUIDITY_RESERVE: self.liquidity_reserve,
            SubAccountId.RP_POOL: self.rp_pool,
        }[sid]

    def balances(self) -> dict[SubAccountId, float]:
        return {sid: sa.balance for sid, sa in self.all_sub_accounts().items()}

    def all_sub_accounts(self) -> dict[SubAccountId, SubAccount]:
        return {
            SubAccountId.EL_POOL: self.el_pool,
            SubAccountId.ULA_BUFFER: self.ula_buffer,
            SubAccountId.LIQUIDITY_RESERVE: self.liquidity_reserve,
            SubAccountId.RP_POOL: self.rp_pool,
        }


@dataclass
class LiquidityReserveSizingSchema:
    """Funding-side-only outflow category schema for LR sizing (claude.md §4.4/§8.6).

    Structure only - the minimum NUMBER is PENDING (claude.md §17
    PENDING_LIQUIDITY_MINIMUM). The schema is the construction (Derivation
    Register I-e); no numbers are guessed here.
    """

    senior_debt_service_and_rollover_stress: float = 0.0
    tier_c_and_tier_d_coupons: float = 0.0
    disbursement_pipeline: float = 0.0
    foreclosure_carrying_costs: float = 0.0
    insurance_fees: float = 0.0
    guarantee_call_settlements_pending_recoveries: float = 0.0
    # PENDING number: the minimum reserve threshold (governance/Orchestrator).
    minimum_reserve_threshold: PendingItem | None = PENDING_LIQUIDITY_MINIMUM

    def total_outflow_schema(self) -> float:
        """Sum of the documented outflow categories (not a minimum threshold)."""
        return sum(
            [
                self.senior_debt_service_and_rollover_stress,
                self.tier_c_and_tier_d_coupons,
                self.disbursement_pipeline,
                self.foreclosure_carrying_costs,
                self.insurance_fees,
                self.guarantee_call_settlements_pending_recoveries,
            ]
        )
