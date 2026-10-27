"""Capital & Leverage Calculator (claude.md §8.2, §4.4).

Why it exists: to continuously answer "is the bank still safe?" in numeric
terms. Computes the three live prudential measures:

  - Tier D / RWA  (>= 12% floor; RWA from Pillar 2's BRR-linked risk weights;
    Tier D = common equity + Perpetual AT1 is the SOLE numerator; Senior Debt
    and Tier C are excluded - Basel-conventional).
  - Portfolio EL  (<= 2% Budgeted Loss).
  - Guarantees-Granted / Guarantees-Received ratio  (the governing
    intermediation-leverage metric; bounded as an ordinary P4 calibration
    parameter, wired and live from Stage 1; breach-vetoed under Track 1).

Inputs: Pillar 2 risk outputs (BRR/PD/LGD/EAD/EL), Part II's live sub-account
balances, and Part II's aggregate given/received guarantee books. Consumes
outputs only (no callback to P2); reads Part II balances.

The input-binding and recompute-trigger structure is a build construction
(Derivation Register I-a); the computation logic is mandated by the Canon.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..domain.buffer_account import BufferAccount, SubAccountId
from ..domain.guarantee_pool import GuaranteePool
from ..contracts.p2_inbound import Pillar2RiskPacket
from .tier_consumption import TierConsumptionService

# BRR -> risk-weight table (Basel-conventional roll-up on the P2 BRR signal).
# BRR is the risk-rating band (1 = safest .. 9 = riskiest); a higher-BRR loan
# of the same size must consume more capital than a low-BRR loan, otherwise
# the Tier D / RWA ratio cannot distinguish a well-underwritten book from a
# reckless one. Values are calibration parameters (mechanism live, numbers
# settable), applied to EAD per facility.
BRR_RISK_WEIGHT: dict[int, float] = {
    1: 0.35,
    2: 0.50,
    3: 0.75,
    4: 1.00,
    5: 1.25,
    6: 1.50,
    7: 1.75,
    8: 2.00,
    9: 2.50,
}


@dataclass(frozen=True)
class CapitalSnapshot:
    """A computed snapshot of the three prudential measures (time series)."""

    tier_d_over_rwa: float
    portfolio_el: float
    guarantees_granted_over_received: float | None
    # supporting figures
    tier_d_amount: float
    rwa: float
    budgeted_loss: float  # the 2% Budgeted Loss threshold (ratio of EL/exp)
    el_pool_balance: float
    given_book: float
    received_book: float
    # risk-weighted breakdown: RWA per facility and the BRR table used.
    rwa_by_facility: dict = field(default_factory=dict)
    risk_weights: dict = field(default_factory=dict)

    # Thresholds (calibration parameters; mechanism live, values settable).
    tier_d_floor: float = 0.12
    budgeted_loss_ratio: float = 0.02

    def tier_d_ok(self) -> bool:
        return self.tier_d_over_rwa >= self.tier_d_floor

    def el_ok(self) -> bool:
        return self.portfolio_el <= self.budgeted_loss_ratio

    def gg_ok(self) -> bool:
        # None means the G/G book is empty (no leverage metric yet) - treated
        # as not-breached. If given book is 0 and received > 0, ratio is 0 (ok).
        if self.guarantees_granted_over_received is None:
            return True
        return self.guarantees_granted_over_received <= 1.0


class CapitalLeverageCalculator:
    """Continuous capital-adequacy and leverage computation."""

    def __init__(
        self,
        tier_consumption: TierConsumptionService,
        tier_d_floor: float = 0.12,
        budgeted_loss_ratio: float = 0.02,
    ):
        self._tiers = tier_consumption
        self.tier_d_floor = tier_d_floor
        self.budgeted_loss_ratio = budgeted_loss_ratio

        # Live ledger of risk packets per facility (from P2 standard cadence +
        # event-driven recompute).
        self._packets: dict[str, Pillar2RiskPacket] = {}
        # Tier D holdings in nominal currency (common equity + Perpetual AT1).
        self.tier_d_amount: float = 0.0
        self._budgeted_loss_amount: float | None = None

    def register_risk_packet(self, packet: Pillar2RiskPacket):
        self._packets[packet.facility_ref] = packet

    def release_risk_packet(self, facility_ref: str):
        """Drop a facility's risk packet once its exposure is gone (close / withhold).

        RWA and portfolio EL are live sums over ``_packets``, so releasing the
        packet removes the loan from the capital roll-up (never-fabricated).
        """
        self._packets.pop(facility_ref, None)

    def reduce_ead_for_repayment(
        self, facility_ref: str, principal_repaid: float
    ) -> Pillar2RiskPacket | None:
        """Update a facility's EAD after a principal repayment.

        The EAD decay depends on the product. For a working-capital line
        (CCF=0.75) a repayment restores undrawn headroom, so ΔEAD = −0.25 ×
        principal. Fully-drawn amortizing products (term/growth loans) reduce
        EAD dollar-for-dollar: ΔEAD = −1.0 × principal — every dollar repaid
        is a dollar of exposure retired. EL is recomputed as PD × LGD × new_EAD.
        """
        pkt = self._packets.get(facility_ref)
        if pkt is None:
            return None
        is_revolving = (pkt.product_type or "").upper() in (
            "WORKING_CAPITAL_LINE",
        )
        ccf = 0.25 if is_revolving else 1.0
        new_ead = max(0.0, pkt.ead - ccf * principal_repaid)
        new_el = round(pkt.pd * pkt.lgd * new_ead, 2)
        updated = Pillar2RiskPacket(
            facility_ref=pkt.facility_ref,
            brr=pkt.brr,
            pd=pkt.pd,
            lgd=pkt.lgd,
            ead=round(new_ead, 2),
            el=new_el,
            model_maturity_stage=pkt.model_maturity_stage,
            brr_pd_grid_version=pkt.brr_pd_grid_version,
            packet_ref=pkt.packet_ref,
            product_type=pkt.product_type,
        )
        self.register_risk_packet(updated)
        return updated

    def set_tier_d_amount(self, amount: float):
        self.tier_d_amount = amount

    def set_budgeted_loss_amount(self, amount: float | None):
        """Budgeted Loss amount (2% of book by policy); settable, else derived."""
        self._budgeted_loss_amount = amount

    # -- RWA and portfolio EL from P2 packets (macro roll-up; P4-side) --------
    def rwa(self) -> float:
        # RWA is a BRR-weighted sum of EAD: a AAA-equivalent MSME loan consumes
        # far less capital than a near-default BRR-9 loan of the same size
        # (Basel-style). P2 scores the BRR; P4 applies the calibration table.
        return round(
            sum(
                p.ead * BRR_RISK_WEIGHT.get(int(p.brr), 1.0)
                for p in self._packets.values()
            ),
            2,
        )

    def rwa_by_facility(self) -> dict[str, float]:
        return {
            ref: round(
                p.ead * BRR_RISK_WEIGHT.get(int(p.brr), 1.0), 2
            )
            for ref, p in self._packets.items()
        }

    def portfolio_el(self) -> float:
        # Portfolio EL is a P4-side computation from P2's per-facility EL
        # (claude.md §9, §5.4 note: portfolio constructs NOT taken from feed).
        return sum(p.el for p in self._packets.values())

    # -- the three live measures ---------------------------------------------
    def snapshot(self, buffer_account: BufferAccount, pool: GuaranteePool) -> CapitalSnapshot:
        rwa = self.rwa()
        tier_d = self.tier_d_amount
        el = self.portfolio_el()
        exposure_base = self.exposure_base()
        el_pool = buffer_account.sub_account(SubAccountId.EL_POOL).balance
        given = pool.given_guarantee_book
        received = pool.received_guarantee_book

        tier_d_over_rwa = (tier_d / rwa) if rwa else 0.0
        # Portfolio EL expressed as a ratio of total EL to the exposure base;
        # the 2% budgeted-loss bound applies to this ratio.
        portfolio_el = (el / exposure_base) if exposure_base else 0.0
        gg_ratio = (given / received) if received else None

        return CapitalSnapshot(
            tier_d_over_rwa=tier_d_over_rwa,
            portfolio_el=portfolio_el,
            guarantees_granted_over_received=gg_ratio,
            tier_d_amount=tier_d,
            rwa=rwa,
            budgeted_loss=self.budgeted_loss_ratio,
            el_pool_balance=el_pool,
            given_book=given,
            received_book=received,
            tier_d_floor=self.tier_d_floor,
            budgeted_loss_ratio=self.budgeted_loss_ratio,
            rwa_by_facility=self.rwa_by_facility(),
            risk_weights=dict(BRR_RISK_WEIGHT),
        )

    def exposure_base(self) -> float:
        # Exposure base (portfolio base for the EL ratio) = sum of EAD,
        # deliberately NOT risk-weighted — portfolio EL is a ratio of expected
        # loss to raw exposure, distinct from risk-weighted RWA.
        return sum(p.ead for p in self._packets.values())

    def evals_to_flags(
        self, snapshot: CapitalSnapshot
    ) -> dict[str, bool]:
        """Convenience: which Track 1 thresholds are currently breached."""
        return {
            "tier_d_below_floor": not snapshot.tier_d_ok(),
            "el_above_budget": not snapshot.el_ok(),
            "gg_ratio_breach": not snapshot.gg_ok(),
        }
