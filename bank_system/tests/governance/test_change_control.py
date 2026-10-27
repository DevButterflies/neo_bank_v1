"""Tests for the Change Control workflow."""


async def test_create_proposal(client):
    resp = await client.post(
        "/api/v1/changes/proposals",
        json={
            "title": "Adjust ABSF weights",
            "change_type": "STRUCTURAL",
            "proposed_by": "Pillar 4",
            "requires_dependency_review": True,
        },
    )
    assert resp.status_code == 201
    proposal = resp.json()
    assert proposal["proposal_number"].startswith("CP-")
    assert proposal["status"] == "SUBMITTED"


async def test_create_g2s_proposal_forces_dependency_review(client):
    resp = await client.post(
        "/api/v1/changes/proposals",
        json={
            "title": "Migrate G to S",
            "change_type": "MIGRATION_G2S",
            "proposed_by": "Governance Committee",
        },
    )
    assert resp.status_code == 201
    proposal = resp.json()
    assert proposal["requires_dependency_review"] is True
    assert proposal["requires_g2s_review"] is True


async def test_ratification_requires_dependency_reviews(client):
    # Create a structural proposal requiring dependency review.
    created = await client.post(
        "/api/v1/changes/proposals",
        json={
            "title": "Structural change requiring review",
            "change_type": "STRUCTURAL",
            "proposed_by": "P2",
            "requires_dependency_review": True,
        },
    )
    pid = created.json()["id"]

    # Attempt ratification before reviews complete -> should fail.
    resp = await client.post(f"/api/v1/changes/proposals/{pid}/ratify")
    assert resp.status_code == 409

    # Submit reviews for pillars 2, 3, 4
    for p in (2, 3, 4):
        await client.post(
            f"/api/v1/changes/proposals/{pid}/dependency-review",
            json={"pillar_number": p, "review_status": "APPROVED"},
        )

    # Ratification should now succeed.
    ratify = await client.post(f"/api/v1/changes/proposals/{pid}/ratify")
    assert ratify.status_code == 200
    assert ratify.json()["status"] == "RATIFIED"


async def test_reject_proposal(client):
    created = await client.post(
        "/api/v1/changes/proposals",
        json={"title": "Reject me", "change_type": "CALIBRATION", "proposed_by": "P4"},
    )
    pid = created.json()["id"]
    resp = await client.post(f"/api/v1/changes/proposals/{pid}/reject")
    assert resp.status_code == 200
    assert resp.json()["status"] == "REJECTED"


async def test_get_proposal_detail(client):
    created = await client.post(
        "/api/v1/changes/proposals",
        json={"title": "Detail me", "change_type": "TIER", "proposed_by": "P4"},
    )
    pid = created.json()["id"]
    resp = await client.get(f"/api/v1/changes/proposals/{pid}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Detail me"
