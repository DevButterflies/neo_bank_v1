"""A default must actually write the residual principal off (B2).

Before the fix ``mark_default`` posted only a zero-amount marker, so every
loan that defaulted kept its full balance sitting in 4110 forever — the
bilan showed 20,200 outstanding while all six facilities were ``CLOSED``.

The marker stays (it is what drives the IFRS9 Stage 3 signal); the write-off
is an additional posting that is skipped entirely when ``loss_amount`` is not
supplied, so every pre-existing caller behaves exactly as before.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bank.pillars.p1 import simulator
from bank.pillars.p3.domain.enums import LoanState, PostingEventType
from bank.pillars.p3.domain.memos import MEMO_DEFAULT_MARKER, MEMO_WRITE_OFF
from bank.pillars.p3.errors import InvalidStateTransitionError
from tests.conftest import make_packet


def _write_offs(orchestrator) -> list:
    return [
        e
        for e in orchestrator.posting_service.posted_events()
        if e.memo == MEMO_WRITE_OFF
    ]


def _markers(orchestrator) -> list:
    return [
        e
        for e in orchestrator.posting_service.posted_events()
        if e.memo == MEMO_DEFAULT_MARKER
    ]


def _prepare(orchestrator, facility_id: str):
    """Drive the facility to the only state a default is legal from."""
    packet = make_packet(facility_id=facility_id)
    orchestrator.originate(packet)
    orchestrator.disburse(facility_id, packet, 10_000.0, "USD")
    orchestrator.mark_delinquent(facility_id, packet)
    return packet


def test_default_without_a_loss_posts_the_marker_only(orchestrator) -> None:
    packet = _prepare(orchestrator, "FAC-WO")

    returned = orchestrator.mark_default("FAC-WO", packet)

    assert returned.memo == MEMO_DEFAULT_MARKER
    assert returned.event_type is PostingEventType.LOSS_RECOVERY
    assert len(_markers(orchestrator)) == 1
    assert _write_offs(orchestrator) == []


def test_default_with_a_loss_posts_a_write_off(orchestrator) -> None:
    packet = _prepare(orchestrator, "FAC-WO")

    marker = orchestrator.mark_default("FAC-WO", packet, 3_200.0, "USD")

    assert marker.memo == MEMO_DEFAULT_MARKER
    assert marker.amount == 0.0

    write_offs = _write_offs(orchestrator)
    assert len(write_offs) == 1
    assert write_offs[0].amount == 3_200.0
    assert write_offs[0].currency == "USD"
    assert write_offs[0].event_type is PostingEventType.LOSS_RECOVERY

    audit = [r.event_type for r in orchestrator.audit_trail.for_facility("FAC-WO")]
    assert audit == [
        "ORIGINATION_RECORDED",
        "DISBURSEMENT",
        "DELINQUENCY",
        "DEFAULT",
        "WRITE_OFF",
    ]


def test_zero_loss_is_treated_as_no_write_off(orchestrator) -> None:
    packet = _prepare(orchestrator, "FAC-WO")

    orchestrator.mark_default("FAC-WO", packet, 0.0, "USD")

    assert _write_offs(orchestrator) == []


def test_write_off_is_posted_once_even_if_default_is_replayed(orchestrator, monkeypatch) -> None:
    packet = _prepare(orchestrator, "FAC-WO")
    # Stand in for a retry that reaches P3 after the state transition already
    # committed: only the write-off idempotency guard is under test here.
    monkeypatch.setattr(orchestrator.state_machine, "mark_default", lambda _f: None)

    orchestrator.mark_default("FAC-WO", packet, 3_200.0, "USD")
    orchestrator.mark_default("FAC-WO", packet, 3_200.0, "USD")

    assert len(_write_offs(orchestrator)) == 1


def test_a_rejected_retry_does_not_post_anything(orchestrator) -> None:
    packet = _prepare(orchestrator, "FAC-WO")
    orchestrator.mark_default("FAC-WO", packet, 3_200.0, "USD")

    before = len(orchestrator.posting_service.posted_events())
    with pytest.raises(InvalidStateTransitionError):
        orchestrator.mark_default("FAC-WO", packet, 3_200.0, "USD")

    assert len(orchestrator.posting_service.posted_events()) == before
    assert len(_write_offs(orchestrator)) == 1


# ---------------------------------------------------------------------------
# P1 hands the real outstanding balance to P3
# ---------------------------------------------------------------------------


def _behavior() -> SimpleNamespace:
    return SimpleNamespace(
        outcome="default",
        disbursed=4_000.0,
        currency="USD",
        repayments=[SimpleNamespace(month=1, interest=100.0, principal=800.0)],
        delinquent_month=2,
        default_month=3,
        recovered_amount=1_500.0,
    )


def _candidate() -> SimpleNamespace:
    packet = make_packet(facility_id="FAC-WO", packet_id="P2-WO")
    return SimpleNamespace(
        id="cand-wo",
        facility_id="FAC-WO",
        status="disbursed",
        application_id="APP-WO",
        sim_state={
            "p3_packet": simulator.packet_to_dict(packet),
            "current_month": 0,
            "disbursed_at_month": 0,
            "payments_made": [],
            "defaulted": False,
            "delinquent": False,
            "closed": False,
            "recoveries": [],
        },
    )


def _patch(monkeypatch, cand) -> SimpleNamespace:
    class _Engine:
        def __init__(self) -> None:
            self.defaults: list[tuple] = []
            self.repayments: list[tuple] = []

        def mark_default(self, facility_id, packet, loss_amount=0.0, currency="USD"):
            self.defaults.append((facility_id, loss_amount, currency))

        def mark_delinquent(self, facility_id, packet):
            return None

        def record_repayment(self, facility_id, packet, interest, principal, currency):
            self.repayments.append((facility_id, principal, currency))

        def close(self, facility_id, packet):
            return None

        def get_facility(self, facility_id):
            return SimpleNamespace(state=LoanState.ACTIVE)

    engine = _Engine()

    monkeypatch.setattr(simulator.service, "hydrate_behavior", lambda _c: _behavior())
    monkeypatch.setattr(simulator.service, "update_status", AsyncMock())

    async def _set_sim_state(_candidate_id, state):
        cand.sim_state = dict(state)

    monkeypatch.setattr(simulator.service, "set_sim_state", _set_sim_state)

    async def _p3_run(fn):
        return fn(engine)

    monkeypatch.setattr(simulator, "_p3_run", _p3_run)
    for name in (
        "mirror_repayment",
        "mirror_default",
        "mirror_recovery",
        "mirror_close",
        "mirror_staging_signal",
    ):
        monkeypatch.setattr(simulator, name, AsyncMock())
    return engine


@pytest.mark.asyncio
async def test_simulator_hands_the_outstanding_balance_to_p3(monkeypatch) -> None:
    """4,000 disbursed, 800 repaid -> the write-off must be 3,200, not 4,000
    and not 0."""
    cand = _candidate()
    engine = _patch(monkeypatch, cand)

    actions = [(await simulator.tick_candidate(cand, m))["action"] for m in (1, 2, 3)]

    assert actions == ["repayment", ["delinquent"], "defaulted"]
    assert engine.defaults == [("FAC-WO", 3_200.0, "USD")]
    simulator.mirror_default.assert_awaited_once_with("FAC-WO", 3_200.0)
