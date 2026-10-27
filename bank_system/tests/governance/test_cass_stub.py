"""Tests for the CASS interface stub."""


async def test_get_stub(client):
    resp = await client.get("/api/v1/cass-stub")
    assert resp.status_code == 200
    stub = resp.json()
    assert stub["source_pillar"] == "P2"
    assert stub["dest_pillar"] == "P4"
    assert "contract shape" in stub["scope"].lower()
    assert len(stub["fields"]) >= 1


async def test_get_stub_scope(client):
    resp = await client.get("/api/v1/cass-stub/scope")
    assert resp.status_code == 200
    scope = resp.json()["scope"].lower()
    assert "contract shape" in scope
    assert "signal derivation" in scope
    assert "outside the stub's scope" in scope
