"""Tests for the Master Lexicon."""


async def test_list_categories(client):
    resp = await client.get("/api/v1/lexicon/categories")
    assert resp.status_code == 200
    cats = resp.json()
    names = [c["name"] for c in cats]
    assert "Architecture and governance" in names
    assert "Credit risk" in names


async def test_get_term(client):
    resp = await client.get("/api/v1/lexicon/terms/pledge release")
    assert resp.status_code == 200
    data = resp.json()
    assert data["term"] == "pledge release"
    assert data["model_scope"] == "G"
    assert data["is_new_in_v34"] is True


async def test_get_term_not_found(client):
    resp = await client.get("/api/v1/lexicon/terms/nonexistentxyz")
    assert resp.status_code == 404


async def test_search_term(client):
    resp = await client.get("/api/v1/lexicon/terms", params={"search": "guarantee call"})
    assert resp.status_code == 200
    results = resp.json()
    assert any(t["term"] == "guarantee call" for t in results)


async def test_validate_terms(client):
    resp = await client.post(
        "/api/v1/lexicon/validate",
        json={"terms": ["pledge release", "smart contract", "P3 shadow ledger", "totally_bogus"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "pledge release" in data["valid"]
    assert "smart contract" in data["valid"]
    # P3 shadow ledger was renamed -> Pillar 3 event log
    assert data["renamed"].get("P3 shadow ledger") == "Pillar 3 event log"
    assert "totally_bogus" in data["invalid"]


async def test_create_term(client):
    resp = await client.post(
        "/api/v1/lexicon/terms",
        json={
            "term": "test-term-xyz",
            "category_id": None,
            "definition": "A test term.",
            "model_scope": "NEUTRAL",
        },
    )
    # category_id None should fail validation -> expect 422
    assert resp.status_code == 422


async def test_renamed_list(client):
    resp = await client.get("/api/v1/lexicon/renamed")
    assert resp.status_code == 200
    renamed = resp.json()
    assert any(t["supersedes"] == "smart contract" for t in renamed)
    assert any(t["supersedes"] == "P3 shadow ledger" for t in renamed)
