"""Veto / freeze notification log service."""

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bank.orchestrator.governance.models.veto_log import VetoEvent
from bank.orchestrator.governance.schemas.veto_log import (
    VetoEventCreate,
    VetoEventResolve,
)


class VetoNotFoundError(Exception):
    pass


async def _next_event_number(db: AsyncSession) -> str:
    result = await db.execute(select(func.count()).select_from(VetoEvent))
    count = result.scalar() or 0
    return f"VE-{count + 1:03d}"


async def record_veto(db: AsyncSession, data: VetoEventCreate) -> VetoEvent:
    """Record a P4 prudential veto signal. Per §8, the freeze resolves at Pillar 2 as
    a withheld/withdrawn output packet — Pillar 4 has no direct per-loan interface with Pillar 3."""
    event = VetoEvent(
        event_number=await _next_event_number(db),
        track=data.track,
        scope=data.scope,
        facility_id=data.facility_id,
        pillar_4_signal=data.pillar_4_signal,
        p2_packet_action=data.p2_packet_action,
        orchestrator_notified_at=datetime.now(timezone.utc),
        governance_review_status="OPEN",
        notes=data.notes,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event


async def list_vetoes(
    db: AsyncSession, track: int | None = None, status: str | None = None
) -> list[VetoEvent]:
    stmt = select(VetoEvent).order_by(VetoEvent.orchestrator_notified_at.desc())
    if track:
        stmt = stmt.where(VetoEvent.track == track)
    if status:
        stmt = stmt.where(VetoEvent.governance_review_status == status)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_veto(db: AsyncSession, event_id) -> VetoEvent | None:
    result = await db.execute(
        select(VetoEvent).where(VetoEvent.id == event_id).limit(1)
    )
    return result.scalar_one_or_none()


async def resolve_veto(
    db: AsyncSession, event_id, data: VetoEventResolve
) -> VetoEvent:
    event = await get_veto(db, event_id)
    if not event:
        raise VetoNotFoundError("Veto event not found.")

    if data.decision == "RESTART_AUTHORIZED":
        event.governance_review_status = "RESTART_AUTHORIZED"
        event.restart_authorized_at = datetime.now(timezone.utc)
        event.restart_authorized_by = data.authorized_by
    else:
        event.governance_review_status = "PACKET_REMAINS_WITHHELD"

    if data.notes:
        event.notes = data.notes

    await db.commit()
    await db.refresh(event)
    return event
