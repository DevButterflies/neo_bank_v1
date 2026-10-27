"""Regression tests: a default-outcome loan MUST converge to CLOSED.

This pins the month-14 "parked loan" bug: the sim's default booking was a
one-shot ``elapsed == default_month`` check. When the P4 guarantee settle
raised (empty received guarantee book), only the P3 default was committed and
``sim["defaulted"]`` was never persisted, leaving the loan permanently
delinquent — with its full outstanding still sitting on the P4 book forever.

Expected behaviour after the fix:
  - the default window is a floor (>=), so a failed tick retries next month;
  - each lifecycle leg (mark, mirror, stage, recover, close, release) is
    retried idempotently via ``_p3_transition_or_accept``; and
  - the loan reaches ``closed`` with the P4 exposure released, so the
    portfolio EL / outstanding become 0 again.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bank.pillars.p1 import simulator
from bank.pillars.p3.domain.enums import LoanState
from bank.pillars.p3.errors import InvalidStateTransitionError
from bank.pillars.p4.contracts.p2_inbound import Pillar2RiskPacket
from bank.pillars.p4.domain.events import Pillar3Event, Pillar3EventType
from bank.pillars.p4.domain.model_maturity import ModelStage
from bank.pillars.p4.integration.pillar4 import Pillar4
from tests.conftest import make_packet


def _default_behavior():
    return SimpleNamespace(
        outcome="default",
        disbursed=4000.0,
        currency="USD",
        repayments=[SimpleNamespace(month=1, interest=100.0, principal=800.0)],
        delinquent_month=2,
        default_month=3,
        recovered_amount=1500.0,
    )


def _candidate(sim_state: dict):
    return SimpleNamespace(
        id="cand-def",
        facility_id="FAC-DEF",
        status="disbursed",
        application_id="APP-DEF",
        sim_state=sim_state,
    )


def _base_sim_state(facility_id="FAC-DEF") -> dict:
    packet = make_packet(facility_id=facility_id, packet_id="P2-DEF")
    return {
        "p3_packet": simulator.packet_to_dict(packet),
        "current_month": 0,
        "disbursed_at_month": 0,
        "payments_made": [],
        "defaulted": False,
        "delinquent": False,
        "closed": False,
        "recoveries": [],
    }


def _patch_runtime(monkeypatch, cand, *, behavior=None, mirrors=None):
    """Wire the simulator's service + mirror seams to a fake that tracks the
    candidate's sim_state exactly like the real persistence layer does."""

    class _NoopEngine:
        def __getattr__(self, name):
            return lambda *a, **k: None

        def get_facility(self, facility_id):
            return SimpleNamespace(state=LoanState.ACTIVE)

    monkeypatch.setattr(
        simulator.service, "hydrate_behavior", lambda _c: behavior or _default_behavior()
    )

    async def _set_sim_state(_candidate_id, state):
        cand.sim_state = dict(state)

    monkeypatch.setattr(simulator.service, "set_sim_state", _set_sim_state)
    monkeypatch.setattr(simulator.service, "update_status", AsyncMock())

    async def _p3_run(fn):
        return fn(_NoopEngine())

    monkeypatch.setattr(simulator, "_p3_run", _p3_run)
    for name in (
        "mirror_repayment",
        "mirror_default",
        "mirror_recovery",
        "mirror_close",
        "mirror_staging_signal",
    ):
        monkeypatch.setattr(simulator, name, AsyncMock(return_value=mirrors.get(name, None) if mirrors else None))


async def _run(cand, start: int, end: int):
    actions = []
    for m in range(start, end + 1):
        ev = await simulator.tick_candidate(cand, m)
        actions.append(ev["action"])
    return actions


@pytest.mark.asyncio
async def test_default_loan_converges_to_closed(monkeypatch):
    cand = _candidate(_base_sim_state())
    _patch_runtime(monkeypatch, cand)

    actions = await _run(cand, 1, 5)

    # m1: repaid, m2: delinquent one-shot, m3: defaulted, m4: recovered+closed
    assert actions == ["repayment", ["delinquent"], "defaulted", "recovered_closed", "noop"]
    assert cand.sim_state["defaulted"] is True
    assert cand.sim_state["closed"] is True
    assert cand.sim_state["recovery_done"] is True
    simulator.mirror_default.assert_awaited_once_with("FAC-DEF", 3200.0)
    simulator.mirror_close.assert_awaited()  # the P4 exposure is released
    # the delay/close path is retried, never one-shot
    assert cand.sim_state["default_loss"] == 3200.0


@pytest.mark.asyncio
async def test_failed_default_is_retried_next_month(monkeypatch):
    cand = _candidate(_base_sim_state())
    _patch_runtime(monkeypatch, cand)

    # The first attempt fails exactly where the real bug did: the P4 settle.
    calls = {"mirror_default": 0}

    async def _flaky_mirror_default(facility_ref, loss):
        calls["mirror_default"] += 1
        if calls["mirror_default"] == 1:
            raise RuntimeError("Cannot draw from pool holding 0.00")

    monkeypatch.setattr(simulator, "mirror_default", _flaky_mirror_default)

    # m3 raises (never persisted: defaulted stays False), m4 retries and lands.
    with pytest.raises(RuntimeError):
        await simulator.tick_candidate(cand, 3)
    assert cand.sim_state["defaulted"] is False

    await simulator.tick_candidate(cand, 4)
    assert cand.sim_state["defaulted"] is True
    assert cand.sim_state["default_mirrored_p4"] is True

    await simulator.tick_candidate(cand, 5)
    assert cand.sim_state["closed"] is True
    assert cand.sim_state["recovery_done"] is True
    assert calls["mirror_default"] == 2


@pytest.mark.asyncio
async def test_p3_transition_or_accept_tolerates_already_committed_state(monkeypatch):
    class _Engine:
        def mark_default(self, *a, **k):
            raise InvalidStateTransitionError("already DEFAULT")

        def get_facility(self, facility_id):
            return SimpleNamespace(state=LoanState.DEFAULT)

    async def _p3_run(fn):
        return fn(_Engine())

    monkeypatch.setattr(simulator, "_p3_run", _p3_run)
    packet = make_packet(facility_id="FAC-DEF", packet_id="P2-DEF")

    # A retry after P3 committed the default must not re-raise forever.
    await simulator._p3_transition_or_accept(
        lambda o: o.mark_default("FAC-DEF", packet), "FAC-DEF", LoanState.DEFAULT
    )


@pytest.mark.asyncio
async def test_p3_transition_or_accept_rejects_unexpected_state(monkeypatch):
    class _Engine:
        def mark_default(self, *a, **k):
            raise InvalidStateTransitionError("not permitted")

        def get_facility(self, facility_id):
            return SimpleNamespace(state=LoanState.ACTIVE)

    async def _p3_run(fn):
        return fn(_Engine())

    monkeypatch.setattr(simulator, "_p3_run", _p3_run)
    packet = make_packet(facility_id="FAC-DEF", packet_id="P2-DEF")

    with pytest.raises(InvalidStateTransitionError):
        await simulator._p3_transition_or_accept(
            lambda o: o.mark_default("FAC-DEF", packet), "FAC-DEF", LoanState.DEFAULT
        )


@pytest.mark.asyncio
async def test_p4_exposure_drops_to_zero_after_default_recovery_close():
    """End-to-end P4 recalc: the user's core demand.

    After a thin-protection default (empty received guarantee book), a recovery
    and a close must RELEASE the packet and return RWA / portfolio EL /
    exposure base to zero — the moment the loan is closed the P1 dashboard
    numbers must stop showing the vanished $3,200 obligation.
    """
    p4 = Pillar4(in_memory_ports=True)
    p4.ports.p2.feed_risk_packet(
        Pillar2RiskPacket(
            facility_ref="FAC-DEF-E2E",
            brr=6,
            pd=0.037668,
            lgd=1.0,
            ead=4750.0,
            el=178.92,
            product_type="WORKING_CAPITAL_LINE",
        )
    )
    p4.ports.p2.feed_staging_signal("FAC-DEF-E2E", 2, None)

    # m1: scheduled repayment — principal 800 (CCF 0.25 => EAD 4750 -> 4550)
    p4.ports.p3.feed_event(
        Pillar3Event(
            event_type=Pillar3EventType.SCHEDULED_REPAYMENT,
            facility_ref="FAC-DEF-E2E",
            amount=900.0,
            principal_component=800.0,
            interest_component=100.0,
        )
    )
    assert p4.ifrs9.facility_stage("FAC-DEF-E2E") == 2
    assert round(p4.capital.exposure_base(), 2) == 4550.0

    # m3: default of 3200 into an EMPTY received book — must settle, not crash.
    # Before the fix this raised and parked the loan forever.
    p4.ports.p3.feed_event(
        Pillar3Event(
            event_type=Pillar3EventType.DEFAULT_OR_WRITE_OFF,
            facility_ref="FAC-DEF-E2E",
            amount=3200.0,
            collateral_leg_amount=0.0,
        )
    )

    # m4: recovery on the collateral leg, then close (mirror_close sequence).
    p4.ports.p3.feed_event(
        Pillar3Event(
            event_type=Pillar3EventType.RECOVERY_COLLATERAL_LEG,
            facility_ref="FAC-DEF-E2E",
            amount=1500.0,
        )
    )
    p4.capital.release_risk_packet("FAC-DEF-E2E")
    p4.ifrs9.release("FAC-DEF-E2E")
    p4.recompute_and_evaluate_track1()

    snap = p4.capital.snapshot(p4.buffer_service.account, p4.pool)
    assert snap.portfolio_el == 0.0
    assert snap.rwa == 0.0
    assert p4.capital.exposure_base() == 0.0