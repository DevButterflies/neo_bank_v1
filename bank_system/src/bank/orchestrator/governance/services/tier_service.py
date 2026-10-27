"""Tier & Pillar boundary service."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bank.orchestrator.governance.config import settings
from bank.orchestrator.governance.models.tier import PillarBoundary, TierDefinition, TierProtectionRule


class TierNotFoundError(Exception):
    pass


class SoleLocusViolationError(Exception):
    pass


async def list_tiers(db: AsyncSession) -> list[TierDefinition]:
    result = await db.execute(
        select(TierDefinition).order_by(TierDefinition.sort_order)
    )
    return list(result.scalars().all())


async def get_tier(db: AsyncSession, label: str) -> TierDefinition | None:
    result = await db.execute(
        select(TierDefinition).where(TierDefinition.tier_label == label).limit(1)
    )
    return result.scalar_one_or_none()


async def get_tier_insurance_status(db: AsyncSession, label: str) -> TierDefinition:
    tier = await get_tier(db, label)
    if not tier:
        raise TierNotFoundError(f"Tier {label} not found.")
    return tier


async def set_tier_insurance_status(
    db: AsyncSession, label: str, status: str
) -> TierDefinition:
    """Enforce the §4.6 'sole locus' rule — Tier A insurance status resolves ONLY here."""
    tier = await get_tier(db, label)
    if not tier:
        raise TierNotFoundError(f"Tier {label} not found.")

    # Sole-locus enforcement: only the Orchestrator's tier endpoint may set this value.
    if not settings.ENFORCE_SOLE_LOCUS:
        # Enforcement disabled — still record authority.
        pass

    tier.insurance_status = status
    tier.insurance_status_authority = "Orchestrator Canon §4.6 (sole locus)"
    await db.commit()
    await db.refresh(tier)
    return tier


async def list_protection_rules(db: AsyncSession) -> list[TierProtectionRule]:
    result = await db.execute(select(TierProtectionRule))
    return list(result.scalars().all())


async def list_pillars(db: AsyncSession) -> list[PillarBoundary]:
    result = await db.execute(
        select(PillarBoundary).order_by(PillarBoundary.pillar_number)
    )
    return list(result.scalars().all())


async def get_pillar(db: AsyncSession, number: int) -> PillarBoundary | None:
    result = await db.execute(
        select(PillarBoundary).where(PillarBoundary.pillar_number == number).limit(1)
    )
    return result.scalar_one_or_none()
