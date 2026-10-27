from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from bank.orchestrator.governance.database import async_session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async database session."""
    async with async_session_factory() as session:
        yield session
