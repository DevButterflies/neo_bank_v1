"""Bilan integration — the balance-sheet invariant, end to end.

Proves the additive bilan does what it promises without disturbing anything
else:

* the router really is registered on the orchestrator root app;
* a real Pillar 3 lifecycle (originate -> disburse -> repay) moves the
  bilan, and ``ecart`` stays ``0.00`` after every single step;
* ``GET /bilan`` is strictly read-only — the ``p3_state_v1``/``p4_state_v1``
  blobs are byte-identical before and after;
* a config update moves **both** faces by the same amount.

Each test owns a fresh temporary KvStore file. ``BANK_ORCH_DB_PATH`` is set
and the settings cache cleared for the duration of the test only, then
restored, so no existing integration test's database is ever shared or
mutated (``bank.orchestrator.config.settings`` itself is never reloaded).
"""

from __future__ import annotations

import os
from contextlib import contextmanager

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from bank.orchestrator.bilan.config import CONFIG_KEY
from bank.orchestrator.bilan.router import router as bilan_router
from bank.orchestrator.bilan import store as bilan_store
from bank.pillars.p3.domain.enums import (
    CollateralTrack,
    MaturityStage,
    P2PacketStatus,
)
from bank.pillars.p3.domain.packet import P2OutputPacket

TIER_D = 100_000.0
DRAW = 20_000.0
INTEREST = 500.0
PRINCIPAL = 4_000.0

PACKET = P2OutputPacket(
    packet_id="P2-BILAN-1",
    facility_id="FAC-BILAN-1",
    status=P2PacketStatus.APPROVED,
    maturity_stage=MaturityStage.SANDBOX,
    brr_pd_grid_version="BRR-GRID-2026-04",
    collateral_track=CollateralTrack.TRACK_1_CLASSICAL,
    packet_version="v1",
    officer_confirmed=True,
    officer_id="OFFICER-BILAN",
)


@pytest.fixture
def bilan_db(tmp_path):
    """Give the bilan a private KvStore file for one test, then put it back."""
    from bank.orchestrator.config import get_orchestrator_settings

    previous = os.environ.get("BANK_ORCH_DB_PATH")
    db = str(tmp_path / "orch.db")
    os.environ["BANK_ORCH_DB_PATH"] = db
    get_orchestrator_settings.cache_clear()
    try:
        yield db
    finally:
        if previous is None:
            os.environ.pop("BANK_ORCH_DB_PATH", None)
        else:
            os.environ["BANK_ORCH_DB_PATH"] = previous
        get_orchestrator_settings.cache_clear()


@pytest.fixture
def client(bilan_db):
    """The bilan router mounted exactly as ``orchestrator/main.py`` mounts it."""
    app = FastAPI()
    app.include_router(bilan_router)
    with TestClient(app) as test_client:
        yield test_client


async def _lifecycle(db: str) -> None:
    """Real Pillar 3 engine writes + a real Pillar 4 capital decision."""
    from bank.pillars.api.p3 import P3Runtime
    from bank.pillars.api.p4 import P4Runtime

    p3 = P3Runtime(db)
    await p3.load()
    await p3.run(lambda o: o.originate(PACKET))
    await p3.run(lambda o: o.disburse(PACKET.facility_id, PACKET, DRAW, "EUR"))

    p4 = P4Runtime(db)
    await p4.load()
    await p4.run(lambda o: o.capital.set_tier_d_amount(TIER_D))


def _line(body: dict, face: str, compte: str) -> float:
    return next(line["montant"] for line in body[face] if line["compte"] == compte)


def _assert_balanced(body: dict) -> None:
    assert body["ecart"] == 0.0, body["totaux"]
    assert body["balanced"] is True
    assert body["totaux"]["actif"] == body["totaux"]["passif"]


def test_bilan_is_registered_and_served_by_the_orchestrator(bilan_db) -> None:
    from bank.orchestrator.main import app

    paths = app.openapi()["paths"]
    assert "/bilan" in paths
    assert "/bilan/config" in paths

    # No ``with``: this deliberately skips the orchestrator lifespan, so the
    # probe registers nothing, seeds nothing and starts no auto-tick.
    bare = TestClient(app)
    response = bare.get("/bilan")
    assert response.status_code == 200, response.text
    body = response.json()
    _assert_balanced(body)
    assert body["totaux"] == {"actif": 0.0, "passif": 0.0}


def test_missing_database_serves_an_empty_balanced_bilan(client) -> None:
    body = client.get("/bilan").json()
    _assert_balanced(body)
    assert body["totaux"] == {"actif": 0.0, "passif": 0.0}
    assert body["sources"] == {"p3_events": 0, "p4_facilities": 0}


async def test_loan_lifecycle_keeps_the_bilan_balanced(client, bilan_db) -> None:
    empty = client.get("/bilan").json()
    _assert_balanced(empty)

    await _lifecycle(bilan_db)

    after_draw = client.get("/bilan").json()
    _assert_balanced(after_draw)
    assert _line(after_draw, "actif", "4110") == DRAW
    assert _line(after_draw, "actif", "5120") == TIER_D - DRAW
    assert _line(after_draw, "passif", "1010") == TIER_D
    assert after_draw["totaux"]["actif"] == TIER_D


async def test_repayment_moves_both_faces(client, bilan_db) -> None:
    from bank.pillars.api.p3 import P3Runtime

    await _lifecycle(bilan_db)
    before = client.get("/bilan").json()

    p3 = P3Runtime(bilan_db)
    await p3.load()
    await p3.run(
        lambda o: o.record_repayment(
            PACKET.facility_id, PACKET, INTEREST, PRINCIPAL, "EUR"
        )
    )

    after = client.get("/bilan").json()
    _assert_balanced(after)
    assert _line(after, "actif", "4110") == DRAW - PRINCIPAL
    assert _line(after, "actif", "5120") == TIER_D - DRAW + PRINCIPAL + INTEREST
    assert _line(after, "passif", "1190") == INTEREST
    assert after["totaux"]["actif"] > before["totaux"]["actif"]
    assert after["mouvements"]["interets"] == INTEREST
    assert after["mouvements"]["remboursements"] == PRINCIPAL


async def test_get_bilan_never_writes_the_pillar_snapshots(client, bilan_db) -> None:
    await _lifecycle(bilan_db)

    before = {
        key: bilan_store.read_json(key, db_path=bilan_db)
        for key in (bilan_store.P3_KEY, bilan_store.P4_KEY, CONFIG_KEY)
    }
    assert before[bilan_store.P3_KEY] is not None
    assert before[bilan_store.P4_KEY] is not None

    for _ in range(3):
        _assert_balanced(client.get("/bilan").json())

    after = {
        key: bilan_store.read_json(key, db_path=bilan_db)
        for key in (bilan_store.P3_KEY, bilan_store.P4_KEY, CONFIG_KEY)
    }
    assert after == before, "GET /bilan mutated the KvStore"


def test_config_update_moves_both_faces_by_the_same_amount(client) -> None:
    before = client.get("/bilan").json()
    assert before["totaux"]["actif"] == 0.0

    with _configured_token("test-token"):
        updated = client.put(
            "/bilan/config",
            json={"depots_clients": 50_000.0},
            headers={"X-Admin-Token": "test-token"},
        )
    assert updated.status_code == 200, updated.text
    assert updated.json()["depots_clients"] == 50_000.0
    assert updated.json()["tresorerie_ouverture"] == 50_000.0

    after = client.get("/bilan").json()
    _assert_balanced(after)
    assert _line(after, "passif", "4210") == 50_000.0
    assert _line(after, "actif", "5120") == 50_000.0
    assert after["totaux"]["actif"] == 50_000.0
    assert after["totaux"]["passif"] == 50_000.0

    reloaded = client.get("/bilan/config").json()
    assert reloaded["depots_clients"] == 50_000.0

    # Config must never be the only thing the endpoint can do: a partial
    # update must not wipe the fields it did not mention.
    assert reloaded["immobilisations"] == 0.0


# ---------------------------------------------------------------------------
# B9 — PUT /bilan/config moves cash, so it must be authenticated and audited
# ---------------------------------------------------------------------------


@contextmanager
def _configured_token(value: str | None):
    from bank.orchestrator.config import get_orchestrator_settings

    previous = os.environ.pop("BANK_ORCH_BILAN_ADMIN_TOKEN", None)
    if value is not None:
        os.environ["BANK_ORCH_BILAN_ADMIN_TOKEN"] = value
    get_orchestrator_settings.cache_clear()
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("BANK_ORCH_BILAN_ADMIN_TOKEN", None)
        else:
            os.environ["BANK_ORCH_BILAN_ADMIN_TOKEN"] = previous
        get_orchestrator_settings.cache_clear()


def test_put_config_without_a_token_is_forbidden(client) -> None:
    with _configured_token("test-token"):
        response = client.put("/bilan/config", json={"depots_clients": 50_000.0})

    assert response.status_code == 403
    # GET endpoints stay open and nothing was written.
    assert client.get("/bilan").status_code == 200
    assert client.get("/bilan/config").status_code == 200
    assert client.get("/bilan/config").json()["depots_clients"] == 0.0


def test_put_config_with_the_wrong_token_is_forbidden(client) -> None:
    with _configured_token("test-token"):
        response = client.put(
            "/bilan/config",
            json={"depots_clients": 50_000.0},
            headers={"X-Admin-Token": "not-the-token"},
        )

    assert response.status_code == 403
    assert client.get("/bilan/config").json()["depots_clients"] == 0.0


def test_put_config_is_forbidden_when_no_token_is_configured(client) -> None:
    with _configured_token(None):
        response = client.put(
            "/bilan/config",
            json={"depots_clients": 50_000.0},
            headers={"X-Admin-Token": "anything"},
        )

    assert response.status_code == 403
    assert "BANK_ORCH_BILAN_ADMIN_TOKEN" in response.json()["detail"]


def test_put_config_with_the_token_is_accepted_and_audited(client, bilan_db) -> None:
    from bank.orchestrator.bilan.router import AUDIT_KEY

    with _configured_token("test-token"):
        first = client.put(
            "/bilan/config",
            json={"depots_clients": 50_000.0},
            headers={"X-Admin-Token": "test-token"},
        )
        second = client.put(
            "/bilan/config",
            json={"immobilisations": 5_000.0},
            headers={"X-Admin-Token": "test-token"},
        )

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert second.json()["depots_clients"] == 50_000.0

    trail = bilan_store.read_json(AUDIT_KEY, db_path=bilan_db)
    assert isinstance(trail, list)
    assert len(trail) == 2

    assert trail[0]["old"]["depots_clients"] == 0.0
    assert trail[0]["new"]["depots_clients"] == 50_000.0
    assert trail[0]["old"]["immobilisations"] == 0.0

    assert trail[1]["old"]["depots_clients"] == 50_000.0
    assert trail[1]["new"]["immobilisations"] == 5_000.0
    assert trail[1]["timestamp"] >= trail[0]["timestamp"]


def test_put_config_with_nothing_to_change_does_not_grow_the_audit(
    client, bilan_db
) -> None:
    from bank.orchestrator.bilan.router import AUDIT_KEY

    with _configured_token("test-token"):
        for _ in range(2):
            response = client.put(
                "/bilan/config",
                json={"depots_clients": 0.0},
                headers={"X-Admin-Token": "test-token"},
            )
            assert response.status_code == 200, response.text

    trail = bilan_store.read_json(AUDIT_KEY, db_path=bilan_db)
    assert not trail, f"expected no audit rows, got {trail!r}"


# ---------------------------------------------------------------------------
# R4 — the config view must not hide whether opening cash was configured,
# and a failed audit append must not fail a change that really happened
# ---------------------------------------------------------------------------


def test_config_view_distinguishes_configured_opening_cash_from_derived(
    client,
) -> None:
    derived = client.get("/bilan/config").json()
    assert derived["tresorerie_ouverture_configured"] is False
    # Still resolved, so a client that only reads the number keeps working.
    assert isinstance(derived["tresorerie_ouverture"], (int, float))

    with _configured_token("test-token"):
        updated = client.put(
            "/bilan/config",
            json={"tresorerie_ouverture": TIER_D},
            headers={"X-Admin-Token": "test-token"},
        )
    assert updated.status_code == 200, updated.text

    configured = client.get("/bilan/config").json()
    assert configured["tresorerie_ouverture_configured"] is True
    assert configured["tresorerie_ouverture"] == TIER_D


def test_a_failed_audit_append_still_returns_200_with_the_change_applied(
    client, monkeypatch
) -> None:
    """Config and audit are two separate KV writes, not a transaction (R4)."""
    from bank.orchestrator.bilan import router as router_module

    async def _boom(*_args, **_kwargs):
        raise RuntimeError("audit store unavailable")

    monkeypatch.setattr(router_module, "_append_audit", _boom)

    with _configured_token("test-token"):
        response = client.put(
            "/bilan/config",
            json={"depots_clients": 50_000.0},
            headers={"X-Admin-Token": "test-token"},
        )

    assert response.status_code == 200, response.text
    assert response.json()["depots_clients"] == 50_000.0
    # The config half committed — that is why a 200 is the honest answer.
    assert client.get("/bilan/config").json()["depots_clients"] == 50_000.0
