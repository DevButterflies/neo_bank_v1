"""The write-off guard has to hold over HTTP, not just in the engine (R1).

``POST /p3/mark-default`` used to accept anything the query string could be
coerced into. The contract the API now owes a caller:

* ``nan`` / ``inf`` / a negative amount never reach the engine (422 from the
  query model itself);
* an amount above the outstanding balance reaches the engine and is refused
  by ``_assert_writable`` with 422 — **before** anything is posted, so the
  ledger keeps only the disbursement it already had.

The P3 app is built on a private SQLite file, and the module-level runtime it
binds to is restored afterwards, so no other test's engine is touched.
"""
from __future__ import annotations

import pytest
from starlette.testclient import TestClient

PACKET = {
    "packet_id": "P2-HTTP-WO",
    "facility_id": "FAC-HTTP-WO",
    "status": "APPROVED",
    "maturity_stage": "SANDBOX",
    "brr_pd_grid_version": "BRR-GRID-2026-04",
    "collateral_track": "TRACK_1_CLASSICAL",
    "packet_version": "v1",
    "officer_confirmed": True,
    "officer_id": "OFFICER-1",
}

BASE = ""  # the P3 ASGI app now serves its router at the app root
MARK_DEFAULT = f"{BASE}/mark-default"

# A write-off is only ever compared against a real disbursement, so the
# facility has to be originated and funded first.
DISBURSED = 10_000.0


@pytest.fixture
def p3_http(tmp_path):
    """Stand the P3 ASGI app up on a throwaway database, then put it back."""
    import bank.pillars.api.p3 as p3_api

    previous = p3_api.runtime
    app = p3_api.make_app(db_path=str(tmp_path / "pillar3.db"))
    try:
        with TestClient(app) as client:
            yield client
    finally:
        p3_api.runtime = previous


@pytest.fixture
def funded(p3_http):
    """One facility with 10,000 drawn and already delinquent — the state a
    write-off is actually reachable from, and the balance it is read against."""
    assert p3_http.post(f"{BASE}/originate", json=PACKET).status_code == 200
    response = p3_http.post(
        f"{BASE}/disburse",
        params={"facility_id": PACKET["facility_id"], "amount": DISBURSED, "currency": "EUR"},
        json=PACKET,
    )
    assert response.status_code == 200, response.text
    response = p3_http.post(
        f"{BASE}/mark-delinquent",
        params={"facility_id": PACKET["facility_id"]},
        json=PACKET,
    )
    assert response.status_code == 200, response.text
    assert p3_http.get(f"{BASE}/postings").json()
    return p3_http


@pytest.mark.parametrize("loss_amount", ["nan", "inf", "-inf", "-1"])
def test_query_model_refuses_unrepresentable_write_offs(
    p3_http, loss_amount
) -> None:
    response = p3_http.post(
        MARK_DEFAULT,
        params={"facility_id": PACKET["facility_id"], "loss_amount": loss_amount},
        json=PACKET,
    )

    assert response.status_code == 422, response.text
    # Rejected by validation, so the engine never ran and nothing was created.
    kinds = {row["type"] for row in response.json()["detail"]}
    assert kinds & {"finite_number", "greater_than_equal"}, kinds
    assert p3_http.get(f"{BASE}/postings").json() == []


def test_write_off_above_outstanding_is_422_and_posts_nothing(funded) -> None:
    before = funded.get(f"{BASE}/postings").json()

    response = funded.post(
        MARK_DEFAULT,
        params={
            "facility_id": PACKET["facility_id"],
            "loss_amount": DISBURSED * 100,
        },
        json=PACKET,
    )

    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert "exceeds the 10000.00 still outstanding" in detail, detail
    # Only the disbursement: no marker, no write-off, no partial default.
    assert funded.get(f"{BASE}/postings").json() == before


def test_write_off_up_to_outstanding_is_accepted(funded) -> None:
    response = funded.post(
        MARK_DEFAULT,
        params={"facility_id": PACKET["facility_id"], "loss_amount": DISBURSED},
        json=PACKET,
    )

    assert response.status_code == 200, response.text
    events = funded.get(f"{BASE}/postings").json()
    write_offs = [e for e in events if e["memo"] == "write-off"]
    assert len(write_offs) == 1
    assert write_offs[0]["amount"] == DISBURSED
