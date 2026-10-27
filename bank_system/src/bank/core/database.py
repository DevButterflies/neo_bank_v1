"""SQLAlchemy asyncio engine/session helpers for per-service SQLite files."""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for all metadata-owned models (governance, etc.)."""


def create_engine(database_url: str) -> AsyncEngine:
    connect_args: dict = {}
    if database_url.startswith("sqlite"):
        # Allow cross-thread use (uvicorn worker threads + tests).
        connect_args["check_same_thread"] = False
    return create_async_engine(database_url, echo=False, connect_args=connect_args)


def make_session_factory(database_url: str) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(create_engine(database_url), expire_on_commit=False)


async def init_models(engine: AsyncEngine, base: type[DeclarativeBase] | None = None) -> None:
    """Create all tables owned by ``base`` (defaults to ``bank.core.Base``)."""
    target = base or Base
    async with engine.begin() as conn:
        await conn.run_sync(target.metadata.create_all)


class SessionDep:
    """Small dependency helper returning ``AsyncGenerator`` sessions per request."""

    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = factory

    async def __call__(self) -> AsyncIterator[AsyncSession]:
        async with self._factory() as session:
            yield session