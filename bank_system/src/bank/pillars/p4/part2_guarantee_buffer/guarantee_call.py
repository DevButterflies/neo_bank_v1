"""Guarantee-Call Settlement Engine (claude.md §8.11, §5.4, §4).

The single most consequential money-moving component - the mechanism that pays
out professional capital when a loss crystallizes.

Settlement sequence (claude.md §5.4):
  1. Draw on the called pool - amount = realized loss NET of the collateral leg.
  2. Passage through reserve/provision sub-accounts - EL Pool, then ULA Buffer
     beyond Budgeted Loss.
  3. Distribution to funders - Senior Institutional Debt, Tier C, Tier D (the
     funders are beneficiaries because they bear the loss the guarantee secures;
     funding-vs-collateral principle).

Pillar boundaries (claude.md §5.4, §4.2) encoded in the build:
  - Pillar 4 computes and settles (draw -> passage -> distribution).
  - Pillar 2 confiend to LGD/EL: it SIZES, does not settle.
  - Pillar 3 records the default + call as event-log entries only; NO
    allocation/burden-sharing/repartition logic.
  - Core banking posts the postings and ALWAYS wins reconciliation disputes.

FOUR-EVENT DISCIPLINE (claude.md §4.4): a guarantee call shares NO vocabulary,
code path, or posting type with pledge release, classical foreclosure, or
redemption. This engine is the CALL path only.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..domain.buffer_account import BufferAccount, SubAccountId
from ..domain.guarantee_pool import GuaranteePool
from ..domain.events import IntraP4Event, IntraP4EventType


@dataclass
class FunderDistribution:
    """Distribution to funders on a guarantee call."""

    distributions: list = field(default_factory=list)  # [{funder_type, amount}]

    def total(self) -> float:
        return sum(d["amount"] for d in self.distributions)


@dataclass
class GuaranteeCallResult:
    settled: bool
    facility_ref: str
    realized_loss_net_collateral_leg: float
    amount_drawn_from_pool: float
    el_pool_absorbed: float
    ula_absorbed: float
    funder_distribution: FunderDistribution
    pool_balance_after: float
    anomaly: str | None = None


class GuaranteeCallSettlementError(Exception):
    """Raised when a call cannot be settled safely (fail loud, never silent)."""


class GuaranteeCallSettlementEngine:
    """Computes and settles the guarantee leg of default realization."""

    def __init__(self, buffer: BufferAccount, pool: GuaranteePool, event_sink=None):
        self._buffer = buffer
        self._pool = pool
        self._event_sink = event_sink or (lambda ev: None)

    def _emit(self, ev):
        self._event_sink(ev)

    def settle(
        self,
        facility_ref: str,
        realized_loss_net_collateral_leg: float,
        distribution_weights: dict | None = None,
    ) -> GuaranteeCallResult:
        """Settle a guarantee call.

        Step 1: draw on the pooled guarantee. The amount is the realized loss
        NET of the collateral leg (claude.md §5.4). The collateral leg and the
        guarantee leg NEVER substitute for each other - this engine only ever
        handles the CALL (guarantee leg).

        Step 2 sizing: the EL Pool absorbs up to whichever is smaller — the
        loss or the EL Pool's CURRENT balance (a currency amount, not a policy
        ratio). Only the true shortfall cascades to the ULA Buffer. Nothing may
        be drawn beyond what the accounts actually hold.
        """
        if realized_loss_net_collateral_leg < 0:
            raise GuaranteeCallSettlementError(
                "Realized loss net of collateral leg cannot be negative"
            )

        drawn = self._draw_pool(realized_loss_net_collateral_leg)

        # Step 2: passage through reserve/provision sub-accounts.
        # The EL Pool absorbs from its ACTUAL available balance. Comparing a
        # single loss event against a policy RATIO (e.g. the 2% budgeted-loss
        # threshold) would size the draw by the wrong unit and could overdraw —
        # the correct sequencing always draws the lesser of (loss, current
        # balance), cascading only the true shortfall to the ULA Buffer.
        cash_to_cover = realized_loss_net_collateral_leg
        el_pool = self._buffer.sub_account(SubAccountId.EL_POOL)
        el_pool_absorbed = min(cash_to_cover, el_pool.balance)
        remaining = cash_to_cover - el_pool_absorbed
        ula_absorbed = min(remaining, self._buffer.sub_account(SubAccountId.ULA_BUFFER).balance)
        # If the ULA Buffer cannot fully absorb, the remainder is a coverage
        # shortfall that the funder distribution step will surface loudly.

        # Debit the sub-accounts (loss absorption).
        el_pool.debit(el_pool_absorbed)
        self._buffer.sub_account(SubAccountId.ULA_BUFFER).debit(ula_absorbed)

        # Step 3: distribution to funders (SID, Tier C, Tier D).
        uncovered = remaining - ula_absorbed
        dist = self._distribute_to_funders(
            cash_to_cover, el_pool_absorbed, ula_absorbed, distribution_weights
        )

        anomaly = None
        if uncovered > 1e-9:
            anomaly = (
                f"ULA Buffer shortfall: {uncovered:.2f} uncovered after EL Pool "
                "and ULA absorption; funder distribution covers only the "
                "absorbed portion."
            )

        self._emit(
            IntraP4Event(
                IntraP4EventType.GUARANTEE_CALL_SETTLED,
                {
                    "facility_ref": facility_ref,
                    "drawn": drawn,
                    "el_pool": el_pool_absorbed,
                    "ula": ula_absorbed,
                    "funders": dist.total(),
                },
            )
        )

        return GuaranteeCallResult(
            settled=True,
            facility_ref=facility_ref,
            realized_loss_net_collateral_leg=realized_loss_net_collateral_leg,
            amount_drawn_from_pool=drawn,
            el_pool_absorbed=el_pool_absorbed,
            ula_absorbed=ula_absorbed,
            funder_distribution=dist,
            pool_balance_after=self._pool.received_guarantee_book,
            anomaly=anomaly,
        )

    def _draw_pool(self, amount: float) -> float:
        """Draw on the called pool (step 1).

        The pooled guarantee is applied to its purpose. The pool's received
        guarantee book (the aggregate macro measure used by adequacy) is reduced
        by the draw, and is validated against the same measure so the draw can
        never exceed what the pool actually holds.

        A shortfall (the pool holding less than the realized loss) is NOT a
        fatal defect: it means the bank's own loss buffer must carry the
        uncovered remainder. The draw therefore floors at the pool's book (the
        received book never goes negative) and the uncovered amount is surfaced
        loudly as a settlement anomaly — a default must never be stranded
        half-booked because the counterparty protection was thin.
        """
        received = self._pool.received_guarantee_book
        drawn = min(amount, received)
        # Reduce the received book by the drawn amount (pool debit).
        self._pool.received_guarantee_book = received - drawn
        return drawn

    def _distribute_to_funders(self, amount, el_pool, ula, weights) -> FunderDistribution:
        """Distribute to SID, Tier C, Tier D (step 3).

        The funders are beneficiaries because they bear the loss the guarantee
        secures. Distribution uses professional-capital tiers; weights settle
        the split (default even if not provided; weighted by the supplied
        weights when given). Only Tier D / Tier C / SID participate - these are
        the LOAN-FUNDING positions, never Tier A / Tier B (collateral).
        """
        absorbed_covered = el_pool + ula
        to_distribute = min(absorbed_covered, amount)
        if weights is None:
            weights = {"SeniorInstitutionalDebt": 1.0, "TierC": 1.0, "TierD": 1.0}
        total_weight = sum(weights.values())
        if total_weight <= 0:
            raise GuaranteeCallSettlementError("Distribution weights must be positive")
        out = []
        for funder, w in weights.items():
            share = to_distribute * (w / total_weight)
            out.append({"funder_type": funder, "amount": round(share, 2)})
        return FunderDistribution(out)
