"""Application smoke tests."""


async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_docs(client):
    resp = await client.get("/docs")
    assert resp.status_code == 200


async def test_openapi_schema(client):
    resp = await client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    assert "paths" in schema
    assert any("/api/v1/canon" in p for p in schema["paths"])
    assert any("/api/v1/interfaces" in p for p in schema["paths"])
