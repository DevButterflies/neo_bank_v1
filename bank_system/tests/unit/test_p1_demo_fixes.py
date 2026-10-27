from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bank.pillars.p1 import simulator
from bank.pillars.p1.router import delete_candidate
from tests.conftest import make_packet


@pytest.mark.asyncio
async def test_tick_candidate_uses_disbursed_month_offset(monkeypatch):
    packet = make_packet(facility_id="FAC-REL")
    cand = SimpleNamespace(
        id="cand-rel",
        facility_id="FAC-REL",
        status="disbursed",
        application_id="APP-REL",
        sim_state={
            "p3_packet": simulator.packet_to_dict(packet),
            "current_month": 0,
            "disbursed_at_month": 3,
            "payments_made": [],
            "defaulted": False,
            "delinquent": False,
            "closed": False,
        },
    )
    behavior = SimpleNamespace(
        disbursed=1200.0,
        currency="USD",
        repayments=[SimpleNamespace(month=1, interest=10.0, principal=100.0)],
        delinquent_month=None,
        default_month=None,
        recovered_amount=None,
    )

    monkeypatch.setattr(simulator.service, "hydrate_behavior", lambda _cand: behavior)
    monkeypatch.setattr(simulator.service, "update_status", AsyncMock())
    monkeypatch.setattr(simulator.service, "set_sim_state", AsyncMock())
    monkeypatch.setattr(simulator, "_p3_run", AsyncMock(return_value=None))
    monkeypatch.setattr(simulator, "mirror_repayment", AsyncMock(return_value=None))

    await simulator.tick_candidate(cand, month=4)

    simulator.service.set_sim_state.assert_awaited_once()
    saved = simulator.service.set_sim_state.await_args.args[1]
    assert saved["current_month"] == 1
    simulator.mirror_repayment.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_candidate_closes_exposure_before_delete(monkeypatch):
    cand = SimpleNamespace(facility_id="FAC-DEL")
    called = {"facility_id": None}

    async def fake_get(candidate_id: str):
        assert candidate_id == "cand-del"
        return cand

    async def fake_delete(candidate_id: str):
        assert candidate_id == "cand-del"
        called["candidate_id"] = candidate_id

    close_mock = AsyncMock()
    monkeypatch.setattr("bank.pillars.p1.router.service.get", fake_get)
    monkeypatch.setattr("bank.pillars.p1.router.service.delete", fake_delete)
    monkeypatch.setattr("bank.pillars.p1.router.mirror_close", close_mock)

    await delete_candidate("cand-del")

    close_mock.assert_awaited_once_with("FAC-DEL")
    assert called["candidate_id"] == "cand-del"
