"""Tests for the Tier & Pillar boundary registry."""


async def test_list_tiers(client):
    resp = await client.get("/api/v1/tiers")
    assert resp.status_code == 200
    tiers = resp.json()
    labels = {t["tier_label"] for t in tiers}
    assert labels == {"A", "B", "C", "D"}


async def test_get_tier(client):
    resp = await client.get("/api/v1/tiers/A")
    assert resp.status_code == 200
    assert resp.json()["tier_label"] == "A"


async def test_tier_a_sole_locus(client):
    resp = await client.get("/api/v1/tiers/A/insurance-status")
    assert resp.status_code == 200
    data = resp.json()
    assert "§4.6" in (data["insurance_status_authority"] or "")


async def test_set_tier_insurance_status(client):
    resp = await client.put(
        "/api/v1/tiers/A/insurance-status",
        json={"status": "Updated conditional status"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["insurance_status"] == "Updated conditional status"
    assert data["insurance_status_authority"] == "Orchestrator Canon §4.6 (sole locus)"


async def test_list_protection_rules(client):
    resp = await client.get("/api/v1/tiers/protection-rules")
    assert resp.status_code == 200
    rules = resp.json()
    assert len(rules) >= 3


async def test_list_pillars(client):
    resp = await client.get("/api/v1/pillars")
    assert resp.status_code == 200
    pillars = resp.json()
    assert len(pillars) == 5
    assert all(p["pillar_number"] in (1, 2, 3, 4, 5) for p in pillars)


async def test_get_pillar(client):
    resp = await client.get("/api/v1/pillars/3")
    assert resp.status_code == 200
    p = resp.json()
    assert p["pillar_name"].lower().startswith("deterministic")


async def test_pillar_perimeter_check_blocked(client):
    resp = await client.post(
        "/api/v1/pillars/3/check-perimeter",
        json={"pillar_number": 3, "action": "Pillar 3 makes a credit decision on facility X"},
    )
    assert resp.status_code == 200
    assert resp.json()["allowed"] is False
    assert resp.json()["violated_rule"] is not None


async def test_pillar_perimeter_check_allowed(client):
    resp = await client.post(
        "/api/v1/pillars/3/check-perimeter",
        json={"pillar_number": 3, "action": "Pillar 3 records a posting to the event log"},
    )
    assert resp.status_code == 200
    assert resp.json()["allowed"] is True
