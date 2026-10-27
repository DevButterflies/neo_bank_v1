"""Tests for the PENDING register + do-not-resolve-in-code discipline."""


async def test_list_seeded_pending_items(client):
    resp = await client.get("/api/v1/pending")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) >= 5
    assert all(i["status"] in ("OPEN", "IN_PROGRESS") for i in items)


async def test_register_item(client):
    resp = await client.post(
        "/api/v1/pending",
        json={
            "title": "New pending test item",
            "category": "INTERFACE",
            "priority": "HIGH",
            "assigned_to": "Pillar 4",
        },
    )
    assert resp.status_code == 201
    item = resp.json()
    assert item["item_number"].startswith("P-")
    assert item["status"] == "OPEN"


async def test_summary(client):
    resp = await client.get("/api/v1/pending/summary")
    assert resp.status_code == 200
    summary = resp.json()
    assert summary["total"] >= 5
    assert summary["open"] >= 5


async def test_resolve_requires_governance_reference(client):
    # Find an open item
    items = (await client.get("/api/v1/pending")).json()
    item_id = items[0]["id"]

    # Resolve without governance_reference -> should be rejected (do-not-resolve-in-code)
    resp = await client.post(
        f"/api/v1/pending/{item_id}/resolve",
        json={"resolution_notes": "some notes"},
    )
    assert resp.status_code == 400
    assert "governance_reference" in resp.json()["detail"]

    # Resolve with governance_reference -> should succeed
    resp = await client.post(
        f"/api/v1/pending/{item_id}/resolve",
        json={
            "resolution_notes": "Resolved by review",
            "governance_reference": "RC-2026-01",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "RESOLVED"


async def test_strike_requires_governance_reference(client):
    items = (await client.get("/api/v1/pending")).json()
    item_id = items[0]["id"]

    # Strike without governance_reference -> rejected
    resp = await client.post(f"/api/v1/pending/{item_id}/strike")
    assert resp.status_code == 400

    # Strike with governance_reference -> success
    resp = await client.post(
        f"/api/v1/pending/{item_id}/strike", params={"governance_reference": "RC-2026-02"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "STRUCK"


async def test_get_item(client):
    items = (await client.get("/api/v1/pending")).json()
    item_id = items[0]["id"]
    resp = await client.get(f"/api/v1/pending/{item_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == item_id
