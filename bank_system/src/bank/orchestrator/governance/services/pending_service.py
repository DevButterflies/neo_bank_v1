"""Cross-pillar PENDING register service (do-not-resolve-in-code discipline)."""

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bank.orchestrator.governance.config import settings
from bank.orchestrator.governance.models.pending_register import PendingItem
from bank.orchestrator.governance.schemas.pending_register import (
    PendingItemCreate,
    PendingItemResolve,
    PendingItemUpdate,
    PendingSummary,
)


class PendingNotFoundError(Exception):
    pass


class PendingDisciplineViolationError(Exception):
    pass


async def _next_item_number(db: AsyncSession) -> str:
    result = await db.execute(select(func.count()).select_from(PendingItem))
    count = result.scalar() or 0
    return f"P-{count + 1:03d}"


async def register_item(db: AsyncSession, data: PendingItemCreate) -> PendingItem:
    item = PendingItem(
        item_number=await _next_item_number(db),
        title=data.title,
        description=data.description,
        category=data.category,
        registered_in_canon=data.registered_in_canon,
        scope_details=data.scope_details,
        priority=data.priority,
        assigned_to=data.assigned_to,
        status="OPEN",
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


async def list_items(
    db: AsyncSession,
    status: str | None = None,
    priority: str | None = None,
    category: str | None = None,
) -> list[PendingItem]:
    stmt = select(PendingItem).order_by(PendingItem.registered_at.desc())
    if status:
        stmt = stmt.where(PendingItem.status == status)
    if priority:
        stmt = stmt.where(PendingItem.priority == priority)
    if category:
        stmt = stmt.where(PendingItem.category == category)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_item(db: AsyncSession, item_id) -> PendingItem | None:
    result = await db.execute(
        select(PendingItem).where(PendingItem.id == item_id).limit(1)
    )
    return result.scalar_one_or_none()


async def update_item(
    db: AsyncSession, item_id, data: PendingItemUpdate
) -> PendingItem:
    item = await get_item(db, item_id)
    if not item:
        raise PendingNotFoundError("PENDING item not found.")
    updates = data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(item, field, value)
    await db.commit()
    await db.refresh(item)
    return item


async def resolve_item(
    db: AsyncSession, item_id, data: PendingItemResolve
) -> PendingItem:
    """Resolve a PENDING item. Enforces the do-not-resolve-in-code discipline:
    an item can only be closed by explicit governance resolution, not by code."""
    item = await get_item(db, item_id)
    if not item:
        raise PendingNotFoundError("PENDING item not found.")

    if settings.ENFORCE_PENDING_DISCIPLINE:
        if not data.resolution_notes or not data.governance_reference:
            raise PendingDisciplineViolationError(
                "Resolving a PENDING item requires BOTH resolution_notes AND a "
                "governance_reference (per the do-not-resolve-in-code discipline, "
                "now codified in the Master Lexicon)."
            )

    item.status = "RESOLVED"
    item.resolution_notes = data.resolution_notes
    item.governance_reference = data.governance_reference
    item.resolved_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(item)
    return item


async def strike_item(
    db: AsyncSession, item_id, governance_reference: str
) -> PendingItem:
    """Strike a PENDING item from the register (closed, will not be resolved)."""
    item = await get_item(db, item_id)
    if not item:
        raise PendingNotFoundError("PENDING item not found.")

    if settings.ENFORCE_PENDING_DISCIPLINE and not governance_reference:
        raise PendingDisciplineViolationError(
            "Striking a PENDING item requires a governance_reference."
        )

    item.status = "STRUCK"
    item.governance_reference = governance_reference
    item.resolved_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(item)
    return item


async def get_summary(db: AsyncSession) -> PendingSummary:
    items = await list_items(db)
    summary = PendingSummary()
    summary.total = len(items)
    summary.open = sum(1 for i in items if i.status in ("OPEN", "IN_PROGRESS"))
    for i in items:
        summary.by_category[i.category] = summary.by_category.get(i.category, 0) + 1
        summary.by_priority[i.priority] = summary.by_priority.get(i.priority, 0) + 1
    return summary
