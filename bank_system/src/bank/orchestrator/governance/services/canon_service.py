"""Canon version store service."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bank.orchestrator.governance.config import settings
from bank.orchestrator.governance.models.canon import CanonVersion, RatificationInstrument
from bank.orchestrator.governance.schemas.canon import CanonVersionCreate, CanonVersionRatify


class CanonConflictError(Exception):
    pass


class CanonNotFoundError(Exception):
    pass


async def get_current_canon(db: AsyncSession) -> CanonVersion | None:
    result = await db.execute(
        select(CanonVersion).where(CanonVersion.is_current.is_(True)).limit(1)
    )
    return result.scalar_one_or_none()


async def list_canon_versions(db: AsyncSession) -> list[CanonVersion]:
    result = await db.execute(
        select(CanonVersion).order_by(CanonVersion.version_number.desc())
    )
    return list(result.scalars().all())


async def get_canon_by_version(db: AsyncSession, version: str) -> CanonVersion | None:
    result = await db.execute(
        select(CanonVersion).where(CanonVersion.version_number == version).limit(1)
    )
    return result.scalar_one_or_none()


async def create_canon_version(
    db: AsyncSession, data: CanonVersionCreate
) -> CanonVersion:
    existing = await get_canon_by_version(db, data.version_number)
    if existing:
        raise CanonConflictError(
            f"Canon version {data.version_number} already exists."
        )
    canon = CanonVersion(
        version_number=data.version_number,
        name=data.name,
        change_summary=data.change_summary,
        lineage_notes=data.lineage_notes,
        status=data.status,
        is_current=False,
    )
    db.add(canon)
    await db.commit()
    await db.refresh(canon)
    return canon


async def ratify_canon_version(
    db: AsyncSession, version: str, data: CanonVersionRatify
) -> CanonVersion:
    canon = await get_canon_by_version(db, version)
    if not canon:
        raise CanonNotFoundError(f"Canon version {version} not found.")
    if canon.status == settings.CANON_STATUS_RATIFIED:
        raise CanonConflictError(f"Canon version {version} already ratified.")

    canon.status = settings.CANON_STATUS_RATIFIED
    canon.ratified_at = datetime.now(timezone.utc)
    canon.ratification_instrument = data.instrument_number

    instrument = RatificationInstrument(
        canon_version_id=canon.id,
        instrument_number=data.instrument_number,
        resolution_ref=data.resolution_ref,
        description=data.description,
        ratified_at=datetime.now(timezone.utc),
    )
    db.add(instrument)

    # Set this as the current version, unset all others.
    all_versions_result = await db.execute(select(CanonVersion))
    for v in all_versions_result.scalars().all():
        v.is_current = v.id == canon.id

    await db.commit()
    await db.refresh(canon)
    return canon


async def supersede_canon_version(db: AsyncSession, version: str) -> CanonVersion:
    canon = await get_canon_by_version(db, version)
    if not canon:
        raise CanonNotFoundError(f"Canon version {version} not found.")
    canon.status = settings.CANON_STATUS_SUPERSEDED
    canon.is_current = False
    await db.commit()
    await db.refresh(canon)
    return canon


async def get_ratifications(
    db: AsyncSession, canon_version_id
) -> list[RatificationInstrument]:
    result = await db.execute(
        select(RatificationInstrument)
        .where(RatificationInstrument.canon_version_id == canon_version_id)
        .order_by(RatificationInstrument.ratified_at)
    )
    return list(result.scalars().all())
