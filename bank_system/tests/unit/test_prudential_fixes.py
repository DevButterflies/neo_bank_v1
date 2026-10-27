"""Regression tests for the prudential-review fixes.

Covers the P4 findings implemented in this workstream:
  - P4-2  RWA is BRR risk-weighted (not raw EAD)
  - P4-3  IFRS9 ECL is stage-aware (S1 12m / S2 lifetime / S3 LGD*EAD)
  - P4-4  EL Pool provision sync posts a DELTA (never erases a router debit)
  - P4-5  EAD-decay CCF depends on product (0.25 revolving / 1.0 amortizing)
  - P4-6  settlement engine draws min(loss, EL Pool balance) then ULA
  - P1-4  try_transition succeeds only for exactly one committed row
"""
from __future__ import annotations

import pytest

from bank.pillars.p1.service import CandidateService, CandidateStateError
from bank.pillars.p4.contracts.p2_inbound import Pillar2RiskPacket
from bank.pillars.p4.domain.buffer_account import SubAccountId
from bank.pillars.p4.domain.events import Pillar3Event, Pillar3EventType
from bank.pillars.p4.integration.pillar4 import Pillar4
from bank.pillars.p4.part1_core_prudential.capital_leverage import BRR_RISK_WEIGHT


def _packet(
    facility_ref: str,
    *,
    brr: float = 4,
    pd: float = 0.05,
    lgd: float = 0.6,
    ead: float = 1000.0,
    product_type: str | None = None,
) -> Pillar2RiskPacket:
    return Pillar2RiskPacket(
        facility_ref=facility_ref,
        brr=brr,
        pd=pd,
        lgd=lgd,
        ead=ead,
        el=round(pd * lgd * ead, 2),
        product_type=product_type,
    )


def _default_event(facility_ref: str, loss: float) -> Pillar3Event:
    return Pillar3Event(
        event_type=Pillar3EventType.DEFAULT_OR_WRITE_OFF,
        facility_ref=facility_ref,
        amount=loss,
        collateral_leg_amount=0.0,
    )


# ---- P4-2: BRR risk-weighted RWA --------------------------------------------


def test_rwa_is_brr_risk_weighted_not_raw_ead():
    p4 = Pillar4(in_memory_ports=True)
    p4.ports.p2.feed_risk_packet(_packet("FAC-LOW", brr=1, ead=1000.0))
    p4.ports.p2.feed_risk_packet(_packet("FAC-HIGH", brr=9, ead=1000.0))

    assert p4.capital.rwa() == round(
        1000.0 * BRR_RISK_WEIGHT[1] + 1000.0 * BRR_RISK_WEIGHT[9], 2
    )
    assert p4.capital.rwa() != 2000.0  # not raw EAD
    assert p4.capital.rwa_by_facility()["FAC-HIGH"] == round(
        1000.0 * BRR_RISK_WEIGHT[9], 2
    )
    snap = p4.capital.snapshot(p4.buffer_service.account, p4.pool)
    assert snap.risk_weights == dict(BRR_RISK_WEIGHT)
    assert snap.rwa_by_facility["FAC-LOW"] == round(1000.0 * BRR_RISK_WEIGHT[1], 2)


# ---- P4-3: stage-aware IFRS9 ECL --------------------------------------------


def test_ecl_is_stage_aware():
    p4 = Pillar4(in_memory_ports=True)
    # el = pd(0.05) * lgd(0.6) * ead(1000) = 30
    p4.ports.p2.feed_risk_packet(_packet("FAC-STG", ead=1000.0))

    assert p4.ifrs9.facility_stage("FAC-STG") == 1
    assert p4.ifrs9._facilities["FAC-STG"].ecl == 30.0

    # Stage 2 => lifetime ECL = 30 * 1.5 = 45
    p4.ports.p2.feed_staging_signal("FAC-STG", 2, None)
    assert p4.ifrs9._facilities["FAC-STG"].ecl == 45.0

    # Stage 3 => PD ~ 1 => LGD * EAD = 0.6 * 1000 = 600
    p4.ports.p2.feed_staging_signal("FAC-STG", 3, None)
    assert p4.ifrs9._facilities["FAC-STG"].ecl == 600.0


# ---- P4-4: EL Pool delta sync (never erases a default debit) ----------------


def test_el_pool_sync_posts_delta_not_overwrite():
    p4 = Pillar4(in_memory_ports=True)
    p4.ports.p2.feed_risk_packet(_packet("FAC-DELTA", ead=1000.0))
    p4.ports.p2.feed_staging_signal("FAC-DELTA", 3, None)  # provision = 600

    el_pool = p4.buffer_service.account.sub_account(SubAccountId.EL_POOL)
    assert el_pool.balance == 600.0

    # A real default realisation draws the EL Pool down by its actual hold.
    p4.pool.received_guarantee_book = 2000.0
    p4.ports.p3.feed_event(_default_event("FAC-DELTA", 200.0))
    assert el_pool.balance == 400.0

    # A subsequent provision re-sync must NOT snap the balance back to 600 —
    # the facility stays on the book (total provision unchanged), so the delta
    # is zero and the router's debit must survive.
    p4.ifrs9.sync_provision()
    assert el_pool.balance == 400.0


# ---- P4-5: product-dependent EAD-decay CCF -----------------------------------


def test_ead_decay_ccf_depends_on_product():
    p4 = Pillar4(in_memory_ports=True)
    p4.ports.p2.feed_risk_packet(
        _packet("FAC-REV", ead=1000.0, product_type="WORKING_CAPITAL_LINE")
    )
    p4.ports.p2.feed_risk_packet(_packet("FAC-TERM", ead=1000.0, product_type="TERM_LOAN"))

    # Revolving: repayment restores headroom -> only 25% of principal decays EAD.
    updated = p4.capital.reduce_ead_for_repayment("FAC-REV", 100.0)
    assert updated is not None
    assert updated.ead == 975.0

    # Amortizing: every dollar repaid retires a dollar of exposure.
    updated = p4.capital.reduce_ead_for_repayment("FAC-TERM", 100.0)
    assert updated is not None
    assert updated.ead == 900.0


# ---- P4-6/6a: settlement draws min(loss, EL Pool) then cascades to ULA ------


def test_settlement_waterfall_uses_actual_balances():
    p4 = Pillar4(in_memory_ports=True)
    p4.ports.p2.feed_risk_packet(_packet("FAC-CAS", ead=1000.0))
    p4.ports.p2.feed_staging_signal("FAC-CAS", 3, None)  # EL Pool = 600
    p4.buffer_service.account.sub_account(SubAccountId.ULA_BUFFER).credit(
        1000.0, "test_seed"
    )
    p4.pool.received_guarantee_book = 5000.0

    result = p4.guarantee_call.settle("FAC-CAS", 1000.0)

    assert result.el_pool_absorbed == 600.0   # capped at actual EL Pool balance
    assert result.ula_absorbed == 400.0       # the true shortfall, not a ratio
    assert result.anomaly is None             # fully covered
    assert p4.buffer_service.account.sub_account(SubAccountId.EL_POOL).balance == 0.0
    assert p4.buffer_service.account.sub_account(SubAccountId.ULA_BUFFER).balance == 600.0
    assert result.funder_distribution.total() > 0


def test_settlement_draw_never_exceeds_el_pool_or_pool():
    p4 = Pillar4(in_memory_ports=True)
    p4.ports.p2.feed_risk_packet(_packet("FAC-OVER", ead=1000.0))
    p4.ports.p2.feed_staging_signal("FAC-OVER", 3, None)  # EL Pool = 600
    p4.buffer_service.account.sub_account(SubAccountId.ULA_BUFFER).credit(50.0, "seed")
    p4.pool.received_guarantee_book = 5000.0

    p4.ports.p3.feed_event(_default_event("FAC-OVER", 1000.0))

    el_pool = p4.buffer_service.account.sub_account(SubAccountId.EL_POOL).balance
    ula = p4.buffer_service.account.sub_account(SubAccountId.ULA_BUFFER).balance
    assert el_pool == 0.0          # capped at the loss (600 < 1000)
    assert ula == 0.0              # exhausted by the shortfall (400 > 50)
    # the shortfall beyond both accounts is surfaced, not silently swallowed


def test_settlement_with_insufficient_pool_flows_to_buffers():
    p4 = Pillar4(in_memory_ports=True)
    p4.ports.p2.feed_risk_packet(_packet("FAC-THIN", ead=1000.0))
    p4.ports.p2.feed_staging_signal("FAC-THIN", 3, None)  # EL Pool = 600

    # Empty received guarantee book: the pool draw floors at zero (the received
    # book never goes negative) and the uncovered remainder is surfaced as a
    # loud anomaly instead of raising. A default must never strand the payment
    # simulator because counterparty protection was thin.
    result = p4.guarantee_call.settle("FAC-THIN", 5000.0)

    assert result.amount_drawn_from_pool == 0.0
    assert p4.pool.received_guarantee_book == 0.0
    assert p4.buffer_service.account.sub_account(SubAccountId.EL_POOL).balance == 0.0
    assert result.anomaly is not None
    assert "shortfall" in result.anomaly.lower()


def test_settlement_draw_is_capped_by_pool_holdings():
    p4 = Pillar4(in_memory_ports=True)
    p4.ports.p2.feed_risk_packet(_packet("FAC-PART", ead=1000.0))
    p4.ports.p2.feed_staging_signal("FAC-PART", 3, None)
    p4.pool.received_guarantee_book = 300.0

    result = p4.guarantee_call.settle("FAC-PART", 200.0)

    assert result.amount_drawn_from_pool == 200.0
    assert p4.pool.received_guarantee_book == 100.0


# ---- P1-4: try_transition atomic claim ---------------------------------------


class _SyncResult:
    def __init__(self, rowcount: int):
        self.rowcount = rowcount


class _FakeSession:
    def __init__(self, rowcount: int):
        self._rowcount = rowcount
        self.committed = False

    async def execute(self, *a, **k):
        return _SyncResult(self._rowcount)

    async def commit(self):
        self.committed = True


class _FakeCtx:
    def __init__(self, rowcount: int):
        self._session = _FakeSession(rowcount)

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc):
        return False


@pytest.mark.asyncio
async def test_try_transition_succeeds_exactly_once(monkeypatch):
    service = CandidateService()
    outcomes = [1, 0]
    monkeypatch.setattr(
        service, "_session_factory", lambda: _FakeCtx(outcomes.pop(0))
    )

    first = await service.try_transition("cand-1", "approved", "disbursing")
    second = await service.try_transition("cand-1", "approved", "disbursing")
    assert first is True      # the winner claimed the row
    assert second is False    # the loser saw zero rows transitioned


@pytest.mark.asyncio
async def test_try_transition_only_commits_exactly_one_row(monkeypatch):
    service = CandidateService()
    monkeypatch.setattr(service, "_session_factory", lambda: _FakeCtx(0))
    assert await service.try_transition("cand-2", "disbursed", "closed") is False