"""Repayment can never drive a facility's principal balance below zero.

Guards two seams for the same invariant (docs/CHANGELOG_bilan.md, B5):

* Pillar 3's ``record_repayment`` rejects an overpayment outright — it must
  leave the posting ledger untouched when it refuses.
* The P1 simulator clamps the scheduled instalment to what is still owed, so
  a schedule whose final instalment is larger than the balance simply pays the
  balance and closes.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bank.pillars.p1 import simulator
from bank.pillars.p3.domain.enums import LoanState
from bank.pillars.p3.errors import RepaymentExceedsOutstandingError
from tests.conftest import make_packet


# ---------------------------------------------------------------------------
# Pillar 3 guard
# ---------------------------------------------------------------------------


def test_partial_repayments_are_allowed(orchestrator) -> None:
    packet = make_packet(facility_id="FAC-GUARD")
    orchestrator.originate(packet)
    orchestrator.disburse("FAC-GUARD", packet, 10_000.0, "USD")

    for principal in (4_000.0, 3_000.0, 3_000.0):
        orchestrator.record_repayment("FAC-GUARD", packet, 150.0, principal, "USD")

    assert orchestrator._principal_totals("FAC-GUARD") == (10_000.0, 10_000.0)


def test_repaying_exactly_to_zero_is_allowed(orchestrator) -> None:
    packet = make_packet(facility_id="FAC-GUARD")
    orchestrator.originate(packet)
    orchestrator.disburse("FAC-GUARD", packet, 5_000.0, "USD")

    orchestrator.record_repayment("FAC-GUARD", packet, 0.0, 5_000.0, "USD")

    assert orchestrator._principal_totals("FAC-GUARD") == (5_000.0, 5_000.0)


def test_repayment_beyond_disbursed_is_rejected_without_posting(orchestrator) -> None:
    packet = make_packet(facility_id="FAC-GUARD")
    orchestrator.originate(packet)
    orchestrator.disburse("FAC-GUARD", packet, 22_000.0, "USD")
    orchestrator.record_repayment("FAC-GUARD", packet, 150.0, 20_000.0, "USD")

    before = len(orchestrator.posting_service.posted_events())
    with pytest.raises(RepaymentExceedsOutstandingError):
        orchestrator.record_repayment("FAC-GUARD", packet, 150.0, 3_000.0, "USD")

    assert len(orchestrator.posting_service.posted_events()) == before


def test_a_single_overpayment_is_rejected(orchestrator) -> None:
    packet = make_packet(facility_id="FAC-GUARD")
    orchestrator.originate(packet)
    orchestrator.disburse("FAC-GUARD", packet, 30_000.0, "USD")

    with pytest.raises(RepaymentExceedsOutstandingError):
        orchestrator.record_repayment("FAC-GUARD", packet, 150.0, 30_001.0, "USD")


def test_negative_principal_is_rejected(orchestrator) -> None:
    packet = make_packet(facility_id="FAC-GUARD")
    orchestrator.originate(packet)
    orchestrator.disburse("FAC-GUARD", packet, 10_000.0, "USD")

    with pytest.raises(ValueError):
        orchestrator.record_repayment("FAC-GUARD", packet, 150.0, -1.0, "USD")


def test_guard_is_skipped_when_no_disbursement_is_on_record(orchestrator) -> None:
    packet = make_packet(facility_id="FAC-GUARD")
    orchestrator.originate(packet)

    assert orchestrator._principal_totals("FAC-GUARD") == (0.0, 0.0)
    # Nothing to cap against yet: must not raise.
    orchestrator._assert_repayable("FAC-GUARD", 500.0, 0.0)


# ---------------------------------------------------------------------------
# Non-finite amounts (bug_bilan_fix_round_2.md, R2)
#
# `nan < 0` and `nan > cap` are both False, so every comparison-shaped guard
# in this file lets NaN straight through. These assert the arithmetic guards
# and the central posting guard both refuse it, and that nothing is posted.
# ---------------------------------------------------------------------------


def _prepare(orchestrator, facility_id: str, amount: float = 10_000.0):
    packet = make_packet(facility_id=facility_id)
    orchestrator.originate(packet)
    orchestrator.disburse(facility_id, packet, amount, "USD")
    return packet


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_principal_is_rejected_without_posting(orchestrator, bad: float) -> None:
    packet = _prepare(orchestrator, "FAC-GUARD")
    before = len(orchestrator.posting_service.posted_events())

    with pytest.raises(ValueError):
        orchestrator.record_repayment("FAC-GUARD", packet, 150.0, bad, "USD")

    assert len(orchestrator.posting_service.posted_events()) == before


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf"), -5.0])
def test_non_finite_or_negative_interest_is_rejected_without_posting(
    orchestrator, bad: float
) -> None:
    packet = _prepare(orchestrator, "FAC-GUARD")
    before = len(orchestrator.posting_service.posted_events())

    with pytest.raises(ValueError):
        orchestrator.record_repayment("FAC-GUARD", packet, bad, 500.0, "USD")

    assert len(orchestrator.posting_service.posted_events()) == before


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_disbursement_is_never_posted(orchestrator, bad: float) -> None:
    """The central guard in ``capture_and_post`` covers every event type.

    The state machine has already moved APPROVED -> ACTIVE by then (it runs
    before the posting), but no ledger row and no audit row is written.
    """
    packet = make_packet(facility_id="FAC-GUARD")
    orchestrator.originate(packet)
    before = len(orchestrator.posting_service.posted_events())

    with pytest.raises(ValueError):
        orchestrator.disburse("FAC-GUARD", packet, bad, "USD")

    assert len(orchestrator.posting_service.posted_events()) == before


def test_a_repayment_that_is_fully_finite_still_posts(orchestrator) -> None:
    """Guard the guard: the checks above must not make every posting fail."""
    packet = _prepare(orchestrator, "FAC-GUARD")

    income, principal = orchestrator.record_repayment(
        "FAC-GUARD", packet, 150.0, 5_000.0, "USD"
    )

    assert income.amount == 150.0
    assert principal.amount == 5_000.0
    assert orchestrator._principal_totals("FAC-GUARD") == (10_000.0, 5_000.0)


# ---------------------------------------------------------------------------
# P1 simulator clamp
# ---------------------------------------------------------------------------


def _behavior(*, disbursed: float, repayments) -> SimpleNamespace:
    return SimpleNamespace(
        outcome="repaid",
        disbursed=disbursed,
        currency="USD",
        repayments=[
            SimpleNamespace(month=month, interest=interest, principal=principal)
            for month, interest, principal in repayments
        ],
        delinquent_month=None,
        default_month=None,
        recovered_amount=0.0,
    )


def _candidate(sim_state: dict):
    packet = make_packet(facility_id="FAC-SIM", packet_id="P2-SIM")
    return SimpleNamespace(
        id="cand-sim",
        facility_id="FAC-SIM",
        status="disbursed",
        application_id="APP-SIM",
        sim_state={
            "p3_packet": simulator.packet_to_dict(packet),
            "current_month": 0,
            "disbursed_at_month": 0,
            "payments_made": [],
            "defaulted": False,
            "delinquent": False,
            "closed": False,
            "recoveries": [],
            **sim_state,
        },
    )


def _patch(monkeypatch, cand, *, behavior):
    """Wire the simulator's persistence and mirror seams to recording fakes."""

    class _Engine:
        def __init__(self) -> None:
            self.repayments: list[tuple] = []
            self.closed = False

        def record_repayment(self, facility_id, packet, interest, principal, currency):
            self.repayments.append((facility_id, interest, principal, currency))

        def close(self, facility_id, packet):
            self.closed = True

        def get_facility(self, facility_id):
            return SimpleNamespace(state=LoanState.ACTIVE)

    engine = _Engine()

    monkeypatch.setattr(simulator.service, "hydrate_behavior", lambda _c: behavior)
    monkeypatch.setattr(simulator.service, "update_status", AsyncMock())

    async def _set_sim_state(_candidate_id, state):
        cand.sim_state = dict(state)

    monkeypatch.setattr(simulator.service, "set_sim_state", _set_sim_state)

    async def _p3_run(fn):
        return fn(engine)

    monkeypatch.setattr(simulator, "_p3_run", _p3_run)
    for name in ("mirror_repayment", "mirror_close"):
        monkeypatch.setattr(simulator, name, AsyncMock())
    return engine


@pytest.mark.asyncio
async def test_simulator_clamps_the_final_instalment_and_closes(monkeypatch) -> None:
    """30,000 disbursed but the schedule asks for 30,000 after 8,000 was paid."""
    cand = _candidate({})
    behavior = _behavior(
        disbursed=30_000.0,
        repayments=[(1, 150.0, 8_000.0), (2, 150.0, 30_000.0)],
    )
    engine = _patch(monkeypatch, cand, behavior=behavior)

    first = await simulator.tick_candidate(cand, 1)
    second = await simulator.tick_candidate(cand, 2)

    assert first["action"] == "repayment"
    assert second["action"] == "repayment_closed"
    # 8,000 then only the 22,000 that was actually still owed.
    assert [round(r[2], 2) for r in engine.repayments] == [8_000.0, 22_000.0]
    assert engine.closed is True
    assert sum(p["principal"] for p in cand.sim_state["payments_made"]) == 30_000.0


@pytest.mark.asyncio
async def test_simulator_skips_posting_when_nothing_is_outstanding(monkeypatch) -> None:
    """A payment falling due on an already-repaid loan posts nothing and closes."""
    cand = _candidate({"payments_made": [{"month": 1, "interest": 0.0, "principal": 5_000.0}]})
    behavior = _behavior(disbursed=5_000.0, repayments=[(2, 25.0, 1_000.0)])
    engine = _patch(monkeypatch, cand, behavior=behavior)

    event = await simulator.tick_candidate(cand, 2)

    assert event["action"] == "repayment_closed"
    assert engine.repayments == []
    assert engine.closed is True
    simulator.mirror_repayment.assert_not_awaited()
    simulator.mirror_close.assert_awaited_once()


@pytest.mark.asyncio
async def test_simulator_does_not_overpay_on_a_healthy_schedule(monkeypatch) -> None:
    """Ordinary schedules are unaffected by the clamp."""
    cand = _candidate({})
    behavior = _behavior(
        disbursed=22_000.0,
        repayments=[(1, 120.0, 6_000.0), (2, 90.0, 8_000.0), (3, 60.0, 8_000.0)],
    )
    engine = _patch(monkeypatch, cand, behavior=behavior)

    actions = [(await simulator.tick_candidate(cand, m))["action"] for m in (1, 2, 3)]

    assert actions == ["repayment", "repayment", "repayment_closed"]
    assert [round(r[2], 2) for r in engine.repayments] == [6_000.0, 8_000.0, 8_000.0]
