import asyncio
import os
import sys

# Ensure project root is on sys.path for imports.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from httpx import ASGITransport, AsyncClient

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

# Test DB: in-memory SQLite.
TEST_DB_URL = "sqlite+aiosqlite://"

from bank.orchestrator.governance.database import Base  # noqa: E402
from bank.orchestrator.governance.seed.seed import seed as seed_data  # noqa: E402


@pytest.fixture
def test_session_factory():
    """Build a test async session factory seeded with canonical data."""
    engine = create_async_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def _prepare():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with factory() as db:
            await seed_data(db)

    asyncio.run(_prepare())
    yield factory
    asyncio.run(engine.dispose())


@pytest.fixture
async def client(test_session_factory):
    """AsyncClient with get_db dependency overridden to the test session."""
    from bank.orchestrator.governance.main import app
    from bank.orchestrator.governance.deps import get_db

    async def override_get_db():
        async with test_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.state.current_canon_status = "RATIFIED"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
