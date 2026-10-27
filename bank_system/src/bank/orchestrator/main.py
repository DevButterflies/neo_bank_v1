"""Orchestrator top-level ASGI application (README: ``uvicorn bank.orchestrator.main:app``).

Mounts the four owned sub-apps under fixed, non-configurable prefixes:

=============  =============================================================
prefix         sub-app
=============  =============================================================
``/governance``  :data:`bank.orchestrator.governance.main:app`
``/p2``          Pillar 2 — stateless facade (module-level ``app``)
``/p3``          Pillar 3 — :func:`bank.pillars.api.p3.make_app` over one KvStore file
``/p4``          Pillar 4 — :func:`bank.pillars.api.p4.make_app` over the same file
=============  =============================================================

Pillars 3 and 4 share the same KvStore SQLite file owned by the orchestrator
(:attr:`~bank.orchestrator.config.OrchestratorSettings.db_path`). ``/ready`` is
the *restart-ok* probe: it re-opens fresh Pillar 3/4 runtimes over that same
file and asserts the rehydrated KvStore snapshots are byte-identical to the
persisted blob — the exact round-trip proved byte-exact by
:file:`tests/pillars/rt3_restart.py` and :file:`tests/pillars/rt4_restart.py`
(and asserted in-process by :file:`tests/integration/`).
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from bank.orchestrator.config import get_orchestrator_settings
from bank.core.openapi_merge import install_merged_openapi
from bank.core.openapi_tags import OPENAPI_TAGS

settings = get_orchestrator_settings()

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("bank.orchestrator.main")

_FIXED_MOUNTS: dict[str, str] = {
    "/governance": "bank.orchestrator.governance.main:app",
    "/p1": "bank.pillars.p1.app:app",
    "/p2": "bank.pillars.api.p2:app",
    "/p3": "bank.pillars.api.p3:app",
    "/p4": "bank.pillars.api.p4:app",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: ensure the owned KvStore file's parent directory exists so a
    relative ``db_path`` (``./data/orchestrator.db``) never fails to open.
    Then seed P1 candidates and start the auto-tick loop."""
    import os

    parent = os.path.dirname(os.path.abspath(settings.db_path))
    os.makedirs(parent, exist_ok=True)

    # Ensure all governance + P1 tables exist (sub-app lifespans do not run
    # under a mount, so this top-level lifespan owns create_all).
    from bank.orchestrator.governance.database import init_models
    await init_models()

    # Seed Tier D capital base (governance-approved initial equity) into the P4
    # runtime once — idempotent (only when uninitialized / after factory reset),
    # so a runtime adjustment via POST /p4/capital/tier-d survives restarts.
    if settings.initial_tier_d_amount > 0:
        try:
            import bank.pillars.api.p4 as p4_pkg
            await p4_pkg.ensure_initial_tier_d(settings.initial_tier_d_amount)
            logger.info("P4 Tier D capital seeded: %.2f", settings.initial_tier_d_amount)
        except Exception as exc:
            logger.warning("P4 Tier D seed skipped: %s", exc)

    # Seed P1 candidates from the portable ``data/candidates/*.json`` exports
    # (idempotent — skips when already populated) — enabled unless
    # BANK_ORCH_SEED_DEMO=false.
    if settings.seed_demo:
        try:
            from bank.pillars.p1.seed_data import seed_candidates_from_exports
            imported = await seed_candidates_from_exports()
            logger.info(
                "P1 demo seed: %d candidate(s) imported from data/candidates/*.json",
                imported,
            )
        except Exception as exc:
            logger.warning("P1 seed skipped: %s", exc)

    # Start P1 auto-tick
    from bank.pillars.p1.simulator import start_auto_tick, stop_auto_tick
    start_auto_tick()

    yield

    stop_auto_tick()


def _make_mounted_apps() -> dict[str, FastAPI]:
    """Import the four sub-apps once and return ``{prefix: app}``.

    Built lazily inside the function so importing ``bank.orchestrator.main``
    (e.g. from a probe) never drags in a mounted Pillar's KvStore file.
    """
    from bank.orchestrator.governance.main import app as governance_app
    from bank.pillars.api.p2 import app as p2_app
    from bank.pillars.api.p3 import make_app as make_p3_app
    from bank.pillars.api.p4 import make_app as make_p4_app
    from bank.pillars.p1.app import app as p1_app

    db = settings.db_path
    return {
        "/governance": governance_app,
        "/p1": p1_app,
        "/p2": p2_app,
        "/p3": make_p3_app(db_path=db),
        "/p4": make_p4_app(
            db_path=db,
            track1_auto_lift_on_sustained_clean=(
                settings.p4_track1_auto_lift_on_sustained_clean
            ),
        ),
    }


_SERVICE_MAP = """\
**Service map** (all mounted under one process, one shared KvStore):

| Prefix | Service | What it owns |
|---|---|---|
| `/governance` | Orchestrator governance | Canon versions, lexicon, tier table, interface rules, CASS stub (CIS-1), SI-1 staging, amendments, veto log, PENDING register |
| `/p1` | Pillar 1 — intake + demo flow | Candidates, scoring/approval/disbursement demo loop, board state, simulation tick |
| `/p2` | Pillar 2 — credit scoring | BRR/PD/LGD/EAD/EL, the versioned BRR→PD grid, early-warning signals, CASS feed contract |
| `/p3` | Pillar 3 — loan execution | Facilities, P2 packets, audit trail, postings, core-banking ledger, reconciliation, lifecycle actions |
| `/p4` | Pillar 4 — prudential layer | Buffer sub-accounts, guarantee-pool adequacy, capital snapshot, IFRS 9 staging, two-track veto, mode gate, pledge intake/release |
| `/bilan` | French-PCG balance sheet | Live Actif/Passif from the shared store, invariant checks, memo items |

**Read the API top-down:** create a candidate in **Pillar 1**, submit → score →
approve → disburse through the demo loop, then watch **Pillar 3** facilities/postings
and **Pillar 4** buffer/capital/veto update. `GET /p4/veto/consult` is the state
**Pillar 2** must consult before confirming a packet — Pillar 3 never sees a veto.
"""

app = FastAPI(
    title="Bank Orchestrator",
    version=settings.app_version,
    description=_SERVICE_MAP,
    openapi_tags=OPENAPI_TAGS,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_mounts = _make_mounted_apps()
for _prefix, _sub in _mounts.items():
    app.mount(_prefix, _sub)

# Compose one merged OpenAPI ("API playbook") at the root /openapi.json and
# /docs: every mounted sub-app's operations, re-prefixed with their mount
# points and with unique operationIds. Per-app /p3/docs etc. keep working.
install_merged_openapi(
    app,
    {
        "governance": ("/governance", _mounts["/governance"]),
        "p1": ("/p1", _mounts["/p1"]),
        "p2": ("/p2", _mounts["/p2"]),
        "p3": ("/p3", _mounts["/p3"]),
        "p4": ("/p4", _mounts["/p4"]),
    },
)

# Additive: register the bilan's own router on the root app (paths ``/bilan``
# and ``/bilan/config``). Imported lazily, like the probes below, so merely
# importing this module never drags the bilan's readers in.
from bank.orchestrator.bilan.router import router as bilan_router  # noqa: E402

app.include_router(bilan_router)

_demo_root = Path(__file__).resolve().parents[3] / "demo"
_demo_static = Path(__file__).resolve().parent / "demo" / "static"
_vite_dist = _demo_root / "dist"

if _vite_dist.exists():
    app.mount("/assets", StaticFiles(directory=str(_vite_dist / "assets")), name="demo_vite_assets")

    @app.get("/", include_in_schema=False)
    async def root() -> FileResponse:
        return FileResponse(_vite_dist / "index.html")
else:
    app.mount("/static", StaticFiles(directory=str(_demo_static)), name="demo_static")

    @app.get("/", include_in_schema=False)
    async def root() -> FileResponse:
        return FileResponse(_demo_static / "index.html")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    favicon_path = _demo_static / "favicon.ico"
    if favicon_path.exists():
        return FileResponse(favicon_path)
    vite_favicon = _vite_dist / "favicon.ico"
    if vite_favicon.exists():
        return FileResponse(vite_favicon)
    return Response(status_code=204)


@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok", "app": settings.app_name, "version": settings.app_version}


@app.get("/ready", tags=["system"])
async def ready():
    """Restart-ok probe — mirrors rt3/rt4: open a fresh Pillar 3 and Pillar 4
    runtime over the same KvStore file and assert the rehydrated snapshot is
    byte-identical to the persisted blob. 503 when any assertion fails."""
    from bank.pillars.api.codec import encode
    from bank.pillars.api.p3 import P3Runtime, STORAGE_KEY as P3_KEY
    from bank.pillars.api.p4 import P4Runtime, STORAGE_KEY as P4_KEY

    db_path = settings.db_path

    p3 = P3Runtime(db_path)
    p4 = P4Runtime(db_path)
    await p3.load()
    await p4.load()

    p3_snap = encode(await p3._snapshot())
    p4_snap = encode(await p4._snapshot())
    p3_stored = await p3.store.get_json(P3_KEY)
    p4_stored = await p4.store.get_json(P4_KEY)

    ok = {
        "p3_restart_ok": p3_snap == p3_stored,
        "p4_restart_ok": p4_snap == p4_stored,
    }
    result = {"status": "ok" if all(ok.values()) else "degraded", "checks": ok}
    if not all(ok.values()):
        raise HTTPException(status_code=503, detail=result)
    return result


def main() -> None:
    """Run via ``uvicorn bank.orchestrator.main:app``."""
    import uvicorn

    uvicorn.run(
        "bank.orchestrator.main:app", host="0.0.0.0", port=8000, log_level="info"
    )


if __name__ == "__main__":
    main()
