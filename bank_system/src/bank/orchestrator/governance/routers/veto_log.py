"""Veto log routes."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from bank.orchestrator.governance.deps import get_db
from bank.orchestrator.governance.schemas.veto_log import (
    VetoEventCreate,
    VetoEventOut,
    VetoEventResolve,
)
from bank.orchestrator.governance.services import veto_service

router = APIRouter(prefix="/vetoes", tags=["veto-log"])


@router.get("", response_model=list[VetoEventOut])
async def list_vetoes(
    track: int | None = Query(None),
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await veto_service.list_vetoes(db, track, status)


@router.post("", response_model=VetoEventOut, status_code=201)
async def record_veto(data: VetoEventCreate, db: AsyncSession = Depends(get_db)):
    return await veto_service.record_veto(db, data)


@router.get("/{event_id}", response_model=VetoEventOut)
async def get_veto(event_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    event = await veto_service.get_veto(db, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Veto event not found.")
    return event


@router.post("/{event_id}/resolve", response_model=VetoEventOut)
async def resolve_veto(
    event_id: uuid.UUID, data: VetoEventResolve, db: AsyncSession = Depends(get_db)
):
    try:
        return await veto_service.resolve_veto(db, event_id, data)
    except veto_service.VetoNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
