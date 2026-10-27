"""PENDING register routes."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from bank.orchestrator.governance.deps import get_db
from bank.orchestrator.governance.schemas.pending_register import (
    PendingItemCreate,
    PendingItemOut,
    PendingItemResolve,
    PendingItemUpdate,
    PendingSummary,
)
from bank.orchestrator.governance.services import pending_service

router = APIRouter(prefix="/pending", tags=["pending-register"])


@router.get("", response_model=list[PendingItemOut])
async def list_items(
    status: str | None = Query(None),
    priority: str | None = Query(None),
    category: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await pending_service.list_items(db, status, priority, category)


@router.post("", response_model=PendingItemOut, status_code=201)
async def register_item(data: PendingItemCreate, db: AsyncSession = Depends(get_db)):
    return await pending_service.register_item(db, data)


@router.get("/summary", response_model=PendingSummary)
async def summary(db: AsyncSession = Depends(get_db)):
    return await pending_service.get_summary(db)


@router.get("/{item_id}", response_model=PendingItemOut)
async def get_item(item_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    item = await pending_service.get_item(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="PENDING item not found.")
    return item


@router.put("/{item_id}", response_model=PendingItemOut)
async def update_item(
    item_id: uuid.UUID, data: PendingItemUpdate, db: AsyncSession = Depends(get_db)
):
    try:
        return await pending_service.update_item(db, item_id, data)
    except pending_service.PendingNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{item_id}/resolve", response_model=PendingItemOut)
async def resolve_item(
    item_id: uuid.UUID, data: PendingItemResolve, db: AsyncSession = Depends(get_db)
):
    try:
        return await pending_service.resolve_item(db, item_id, data)
    except pending_service.PendingNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except pending_service.PendingDisciplineViolationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{item_id}/strike", response_model=PendingItemOut)
async def strike_item(
    item_id: uuid.UUID,
    governance_reference: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await pending_service.strike_item(db, item_id, governance_reference)
    except pending_service.PendingNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except pending_service.PendingDisciplineViolationError as e:
        raise HTTPException(status_code=400, detail=str(e))
