"""Pillar 1 FastAPI assembly — candidates + demo flow.

Standalone: ``uvicorn bank.pillars.p1.app:app --reload``
Composed:   ``/p1`` mount in ``bank.orchestrator.main``.
"""
from __future__ import annotations

import contextlib

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from bank.core.config import get_settings
from bank.core.errors import BankError, NotFoundError
from bank.core.openapi_tags import OPENAPI_TAGS
from bank.pillars.p1.broker import publish_event
from bank.pillars.p1.router import router as crud_router
from bank.pillars.p1.routes import router as demo_router
from bank.pillars.p1.seed_data import seed_candidates
from bank.pillars.p1.simulator import start_auto_tick, stop_auto_tick


async def _bank_error_handler(request, exc: BankError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


async def _not_found_handler(request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": exc.detail})


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    from bank.orchestrator.governance.database import init_models
    await init_models()
    await seed_candidates()
    start_auto_tick()
    yield
    stop_auto_tick()


def build_p1_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Pillar 1 — Candidates + Demo Flow",
        version=settings.app_version,
        description=(
            "Borrower intake and the end-to-end demo loop: create/import "
            "candidates, run submit → score → approve → disburse through "
            "Pillars 2/3/4, and drive the board via the simulation tick."
        ),
        docs_url="/docs",
        openapi_url="/openapi.json",
        openapi_tags=OPENAPI_TAGS,
        lifespan=lifespan,
    )
    app.add_exception_handler(BankError, _bank_error_handler)
    app.add_exception_handler(NotFoundError, _not_found_handler)
    app.include_router(crud_router)
    app.include_router(demo_router)

    @app.get("/health", include_in_schema=False)
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = build_p1_app()
