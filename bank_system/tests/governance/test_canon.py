"""Tests for the Canon registry."""


async def test_get_current_canon(client):
    resp = await client.get("/api/v1/canon/current")
    assert resp.status_code == 200
    data = resp.json()
    assert data["version_number"] == "3.4"
    assert data["status"] == "RATIFIED"
    assert data["is_current"] is True


async def test_list_versions(client):
    resp = await client.get("/api/v1/canon/versions")
    assert resp.status_code == 200
    versions = resp.json()
    numbers = [v["version_number"] for v in versions]
    assert "2.0" in numbers
    assert "3.0" in numbers
    assert "3.4" in numbers


async def test_get_version(client):
    resp = await client.get("/api/v1/canon/versions/3.4")
    assert resp.status_code == 200
    data = resp.json()
    assert data["version_number"] == "3.4"
    assert len(data["ratification_instruments"]) >= 1


async def test_create_and_ratify_version(client):
    resp = await client.post(
        "/api/v1/canon/versions",
        json={
            "version_number": "3.5",
            "name": "Orchestrator Canon V3.5",
            "status": "PENDING",
        },
    )
    assert resp.status_code == 201
    created = resp.json()
    assert created["status"] == "PENDING"
    assert created["is_current"] is False

    ratify = await client.post(
        "/api/v1/canon/versions/3.5/ratify",
        json={
            "instrument_number": "RI-4",
            "resolution_ref": "Resolution 5",
            "description": "Test ratification",
        },
    )
    assert ratify.status_code == 200
    ratified = ratify.json()
    assert ratified["status"] == "RATIFIED"
    assert ratified["is_current"] is True

    # Old 3.4 should now not be current.
    old = await client.get("/api/v1/canon/current")
    assert old.json()["version_number"] == "3.5"


async def test_duplicate_version_conflict(client):
    resp = await client.post(
        "/api/v1/canon/versions",
        json={"version_number": "3.4", "name": "dup"},
    )
    assert resp.status_code == 409
