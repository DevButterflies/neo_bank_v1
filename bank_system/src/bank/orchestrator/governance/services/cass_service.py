"""CASS interface stub service."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bank.orchestrator.governance.models.cass_stub import CassStubMetadata
from bank.orchestrator.governance.schemas.cass_stub import CassStubMetadataIn


class CassStubNotFoundError(Exception):
    pass


async def get_current_stub(db: AsyncSession) -> CassStubMetadata | None:
    result = await db.execute(
        select(CassStubMetadata)
        .options(selectinload(CassStubMetadata.fields))
        .order_by(CassStubMetadata.version.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def create_or_update_stub(
    db: AsyncSession, data: CassStubMetadataIn
) -> CassStubMetadata:
    existing = await get_current_stub(db)
    if existing:
        # Treat as an update of the existing stub's metadata.
        existing.version = data.version
        existing.scope = data.scope
        existing.source_pillar = data.source_pillar
        existing.dest_pillar = data.dest_pillar
        existing.refresh_cadence = data.refresh_cadence
        existing.failure_semantics = data.failure_semantics
        stub = existing
    else:
        stub = CassStubMetadata(
            version=data.version,
            scope=data.scope,
            source_pillar=data.source_pillar,
            dest_pillar=data.dest_pillar,
            refresh_cadence=data.refresh_cadence,
            failure_semantics=data.failure_semantics,
        )
        db.add(stub)
    await db.commit()
    await db.refresh(stub)
    result = await db.execute(
        select(CassStubMetadata)
        .options(selectinload(CassStubMetadata.fields))
        .where(CassStubMetadata.id == stub.id)
    )
    return result.scalar_one()
