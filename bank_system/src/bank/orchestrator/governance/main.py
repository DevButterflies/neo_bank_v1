import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from bank.core.openapi_tags import OPENAPI_TAGS
from bank.orchestrator.governance.config import settings
from bank.orchestrator.governance.database import init_models
from bank.orchestrator.governance.middleware.audit import AuditAndCanonEnforcementMiddleware
from bank.orchestrator.governance.routers import (
    canon,
    cass_stub,
    change_control,
    interface_rules,
    lexicon,
    pending_register,
    staging,
    tier,
    veto_log,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger("orchestrator")

from sqlalchemy import select
from bank.orchestrator.governance.models.canon import CanonVersion
from bank.orchestrator.governance.database import async_session_factory


async def load_canon_status(app: FastAPI) -> None:
    """Load the current canon status into app state for middleware enforcement.

    Also called by the orchestrator: Starlette never runs a mounted sub-app's
    lifespan, so without it every mutating governance request fails with 500.
    """
    async with async_session_factory() as db:
        result = await db.execute(
            select(CanonVersion).where(CanonVersion.is_current.is_(True)).limit(1)
        )
        current = result.scalar_one_or_none()
        app.state.current_canon_status = current.status if current else "NONE"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize DB and load current canon status into app state."""
    if settings.AUTO_CREATE_TABLES:
        await init_models()
        logger.info("Database tables ensured.")

    await load_canon_status(app)

    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Orchestrator Governance Layer for the Neo-Bank MSME Operating System, "
        "implemented against Orchestrator Canon V3.4 (ratified). Owns the "
        "canon versions, Master Lexicon, canonical tier table, inter-pillar "
        "interface rules, the CIS-1 CASS contract stub, SI-1 staging, "
        "amendment proposals, the veto log, and the PENDING register."
    ),
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
app.add_middleware(AuditAndCanonEnforcementMiddleware)

API = settings.API_PREFIX

app.include_router(canon.router, prefix=API)
app.include_router(lexicon.router, prefix=API)
app.include_router(tier.router, prefix=API)
app.include_router(interface_rules.router, prefix=API)
app.include_router(cass_stub.router, prefix=API)
app.include_router(staging.router, prefix=API)
app.include_router(change_control.router, prefix=API)
app.include_router(veto_log.router, prefix=API)
app.include_router(pending_register.router, prefix=API)


@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}


@app.get("/", include_in_schema=False)
async def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "api": settings.API_PREFIX,
    }
