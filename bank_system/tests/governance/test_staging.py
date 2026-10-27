"""Tests for the Staging / Mode registry (SI-1)."""


async def test_initial_mode_conventional(client):
    resp = await client.get("/api/v1/staging/mode")
    assert resp.status_code == 200
    assert resp.json()["current_mode"] == "CONVENTIONAL"


async def test_initial_stage_zero(client):
    resp = await client.get("/api/v1/staging/stage")
    assert resp.status_code == 200
    assert resp.json()["current_stage"] == 0


async def test_gates_pending(client):
    resp = await client.get("/api/v1/staging/gates")
    assert resp.status_code == 200
    gates = resp.json()
    labels = {g["gate_label"] for g in gates}
    assert labels == {"G0", "G1", "G2", "G3"}
    assert all(g["status"] == "PENDING" for g in gates)


async def test_adaptive_inactive_by_default(client):
    resp = await client.get("/api/v1/staging/is-adaptive-active")
    assert resp.status_code == 200
    assert resp.json()["adaptive_active"] is False


async def test_switch_to_adaptive(client):
    resp = await client.put(
        "/api/v1/staging/mode",
        json={"new_mode": "ADAPTIVE", "change_rationale": "Governance ruling"},
    )
    assert resp.status_code == 200
    assert resp.json()["current_mode"] == "ADAPTIVE"

    # Adaptive should now be active
    check = await client.get("/api/v1/staging/is-adaptive-active")
    assert check.json()["adaptive_active"] is True


async def test_switch_back_to_conventional(client):
    await client.put(
        "/api/v1/staging/mode", json={"new_mode": "ADAPTIVE", "change_rationale": "to adaptive"}
    )
    resp = await client.put(
        "/api/v1/staging/mode", json={"new_mode": "CONVENTIONAL", "change_rationale": "fallback"}
    )
    assert resp.status_code == 200
    assert resp.json()["current_mode"] == "CONVENTIONAL"


async def test_invalid_mode_rejected(client):
    resp = await client.put(
        "/api/v1/staging/mode", json={"new_mode": "INVALID", "change_rationale": "x"}
    )
    assert resp.status_code == 422


async def test_clear_gate(client):
    resp = await client.post("/api/v1/staging/gates/G0/clear")
    assert resp.status_code == 200
    assert resp.json()["status"] == "CLEARED"


async def test_block_gate(client):
    resp = await client.post(
        "/api/v1/staging/gates/G1/block", params={"notes": "Spec not finalized"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "BLOCKED"
