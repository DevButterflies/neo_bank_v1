"""Shared FastAPI factory: uniform /health, error mapping, and router mounting."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse

from bank.core.config import Settings
from bank.core.errors import BankError, NotFoundError
from bank.core.openapi_tags import OPENAPI_TAGS

health_router = APIRouter(tags=["health"])


def _default_tags() -> list[dict]:
    """Shared tag metadata so every service groups its operations the same way."""
    return OPENAPI_TAGS


@health_router.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    return {"status": "ok"}


async def _bank_error_handler(request: Request, exc: BankError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


async def _not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": exc.detail})


def build_app(
    *,
    service: str,
    settings: Settings,
    routers: list[tuple[str, APIRouter]] | None = None,
    on_startup: list[Callable[[], Awaitable[None] | None]] | None = None,
    description: str | None = None,
    openapi_tags: list[dict] | None = None,
) -> FastAPI:
    """Build a standard bank service app.

    ``routers`` are ``(prefix, router)`` pairs; the prefix is applied
    verbatim (``""`` = no extra prefix — the caller owns the public path
    shape). The shared ``/health`` is always registered at the app root.
    """
    app = FastAPI(
        title=service,
        version=settings.app_version,
        description=description,
        docs_url="/docs",
        openapi_url="/openapi.json",
        openapi_tags=openapi_tags or _default_tags(),
    )
    app.add_exception_handler(BankError, _bank_error_handler)

    app.include_router(health_router)

    for prefix, router in (routers or []):
        app.include_router(router, prefix=prefix)

    if on_startup:

        @app.on_event("startup")
        async def _startup() -> None:  # pragma: no cover - exercised by composition
            for callback in on_startup:
                result = callback()
                if hasattr(result, "__await__"):
                    await result

    return app