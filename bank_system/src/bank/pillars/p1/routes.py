"""P1 demo routes — SSE stream, state snapshot, tick, seed profiles, reset.

Mounted at ``/p1/demo``.
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from bank.pillars.p1.broker import BROKER, publish_event
from bank.pillars.p1.schemas import ResetOut, SeedOut, TickOut
from bank.pillars.p1.seed_data import list_seed_profiles, seed_candidates
from bank.pillars.p1.simulator import tick
from bank.pillars.p1.state import build_demo_state
from bank.pillars.p1.service import service

router = APIRouter(prefix="/demo", tags=["p1-demo"])


# ---- SSE --------------------------------------------------------------------


@router.get("/events/sse", include_in_schema=False)
async def sse_events(request: Request):
    queue = BROKER.subscribe()

    async def stream():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30)
                    yield f"data: {__import__('json').dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield "data: {}\n\n"
        finally:
            BROKER.unsubscribe(queue)

    return StreamingResponse(stream(), media_type="text/event-stream")


# ---- state ------------------------------------------------------------------


@router.get(
    "/state",
    summary="Demo board state",
    description=(
        "One snapshot for the demo board: candidates by status, facilities, "
        "book KPIs, IFRS 9 map, and the live P4 veto/mode state. Pure GET — "
        "does not publish to the SSE bus."
    ),
)
async def get_state():
    # Deliberately does NOT publish: publishing on a pure GET would flood the
    # SSE bus with a frame on every poll, and each frame's invalidation in the
    # client triggers another GET — an SSE<->refetch recursion storm that leaves
    # the board racing out-of-order snapshots. The GET response carries the
    # state itself; SSE is reserved for state-CHANGES (tick / reset / actions).
    return await build_demo_state()


# ---- tick -------------------------------------------------------------------


@router.post(
    "/tick",
    response_model=TickOut,
    summary="Advance the simulation one month",
    description=(
        "Move every disbursed facility one month along its payment "
        "behaviour (repayment / delinquency / default / recovery), then "
        "publish the new state on the SSE bus."
    ),
)
async def post_tick():
    result = await tick()
    state = await build_demo_state()
    await publish_event("tick", {"tick": result, "state": state})
    return {"tick": result, "state": state}


# ---- seed profiles ----------------------------------------------------------


@router.get(
    "/profiles",
    summary="List seed profiles",
    description=(
        "The demo seed profiles (data tier, expected outcome, tagline) the "
        "board can instantiate."
    ),
)
async def get_profiles():
    return list_seed_profiles()


# ---- seed trigger -----------------------------------------------------------


@router.post(
    "/seed",
    response_model=SeedOut,
    summary="Seed the demo pipeline",
    description="Instantiate every seed profile as a fresh candidate.",
)
async def post_seed():
    count = await seed_candidates()
    state = await build_demo_state()
    await publish_event("state_update", state)
    return {"seeded": count}


# ---- reset ------------------------------------------------------------------


@router.post(
    "/reset",
    response_model=ResetOut,
    summary="Factory reset the demo bank",
    description=(
        "Wipe candidates, facilities, postings and ledger in P1/P3/P4, "
        "re-seed the governance-approved initial Tier D capital base, and "
        "return the board to month 0."
    ),
)
async def post_reset():
    await service.reset_all()
    from bank.pillars.p1.mirror import p3_runtime, p4_runtime
    await p3_runtime().reset()
    await p4_runtime().reset()
    # Factory reset zeroed Tier D — re-apply the governance-approved initial
    # capital base so a fresh demo bank is never unfunded.
    from bank.orchestrator.config import get_orchestrator_settings
    from bank.pillars.api.p4 import ensure_initial_tier_d
    await ensure_initial_tier_d(get_orchestrator_settings().initial_tier_d_amount)
    import bank.pillars.p1.simulator as sim
    await sim.reset_sim_month()
    state = await build_demo_state()
    await publish_event("reset", state)
    return {"status": "reset", "state": state}
