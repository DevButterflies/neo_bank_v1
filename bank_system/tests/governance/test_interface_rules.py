"""Tests for the interface rules registry."""


async def test_list_all_interfaces(client):
    resp = await client.get("/api/v1/interfaces")
    assert resp.status_code == 200
    rules = resp.json()
    numbers = {r["rule_number"] for r in rules}
    assert numbers == {"6.1", "6.2", "6.3", "6.4", "6.5", "6.6", "6.7"}


async def test_get_guarantee_call_interface(client):
    resp = await client.get("/api/v1/interfaces/6.7")
    assert resp.status_code == 200
    rule = resp.json()
    assert rule["name"] == "Guarantee Call — Guarantee Leg of Default Realization"


async def test_ifrs9_bypasses_pillar3(client):
    resp = await client.get("/api/v1/interfaces/6.1")
    assert resp.json()["bypasses_pillar3"] is True


async def test_validate_flow_p2_p4(client):
    resp = await client.post(
        "/api/v1/interfaces/validate-flow",
        json={"source": "P2", "destination": "P4"},
    )
    assert resp.status_code == 200
    data = resp.json()
    numbers = {r["rule_number"] for r in data["rules"]}
    # IFRS9 staging (6.1) and CASS feed (6.6) are P2->P4 and bypass P3
    assert "6.1" in numbers
    assert "6.6" in numbers
    assert data["bypasses_pillar3"] is True


async def test_get_interface_not_found(client):
    resp = await client.get("/api/v1/interfaces/9.9")
    assert resp.status_code == 404
