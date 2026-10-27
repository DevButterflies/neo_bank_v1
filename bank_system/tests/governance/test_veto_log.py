"""Tests for the Veto / freeze notification log."""


async def test_record_veto(client):
    resp = await client.post(
        "/api/v1/vetoes",
        json={
            "track": 1,
            "scope": "facility",
            "facility_id": "fac-001",
            "pillar_4_signal": "Capital ratio breach",
            "p2_packet_action": "WITHHELD",
        },
    )
    assert resp.status_code == 201
    event = resp.json()
    assert event["event_number"].startswith("VE-")
    assert event["governance_review_status"] == "OPEN"
    assert event["p2_packet_action"] == "WITHHELD"


async def test_list_vetoes(client):
    await client.post(
        "/api/v1/vetoes",
        json={"track": 2, "scope": "portfolio", "p2_packet_action": "WITHDRAWN"},
    )
    resp = await client.get("/api/v1/vetoes")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


async def test_resolve_veto_restart_authorized(client):
    created = await client.post(
        "/api/v1/vetoes",
        json={"track": 1, "scope": "facility", "p2_packet_action": "WITHHELD"},
    )
    eid = created.json()["id"]
    resp = await client.post(
        f"/api/v1/vetoes/{eid}/resolve",
        json={"decision": "RESTART_AUTHORIZED", "authorized_by": "Governance Committee"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["governance_review_status"] == "RESTART_AUTHORIZED"
    assert data["restart_authorized_at"] is not None


async def test_resolve_veto_packet_remains_withheld(client):
    created = await client.post(
        "/api/v1/vetoes",
        json={"track": 2, "scope": "portfolio", "p2_packet_action": "WITHDRAWN"},
    )
    eid = created.json()["id"]
    resp = await client.post(
        f"/api/v1/vetoes/{eid}/resolve",
        json={"decision": "PACKET_REMAINS_WITHHELD"},
    )
    assert resp.status_code == 200
    assert resp.json()["governance_review_status"] == "PACKET_REMAINS_WITHHELD"
