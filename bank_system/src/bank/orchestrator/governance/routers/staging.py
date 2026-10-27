from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from bank.orchestrator.governance.deps import get_db
from bank.orchestrator.governance.schemas.staging import (
    GateStateOut,
    ModeChangeIn,
    ModeStateOut,
    StageStateOut,
)
from bank.orchestrator.governance.services import staging_service

router = APIRouter(prefix="/staging", tags=["staging-mode"])


@router.get("/mode", response_model=ModeStateOut)
async def get_mode(db: AsyncSession = Depends(get_db)):
    mode = await staging_service.get_current_mode(db)
    if not mode:
        raise HTTPException(status_code=404, detail="No mode state set. Run seeding first.")
    return mode


@router.put("/mode", response_model=ModeStateOut)
async def set_mode(data: ModeChangeIn, db: AsyncSession = Depends(get_db)):
    try:
        return await staging_service.set_mode(db, data)
    except staging_service.StagingConflictError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/stage", response_model=StageStateOut)
async def get_stage(db: AsyncSession = Depends(get_db)):
    stage = await staging_service.get_current_stage(db)
    if not stage:
        raise HTTPException(status_code=404, detail="No stage state set. Run seeding first.")
    return stage


@router.put("/stage", response_model=StageStateOut)
async def set_stage(stage: int = Query(...), db: AsyncSession = Depends(get_db)):
    try:
        return await staging_service.set_stage(db, stage)
    except staging_service.StagingConflictError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/gates", response_model=list[GateStateOut])
async def list_gates(db: AsyncSession = Depends(get_db)):
    return await staging_service.list_gates(db)


@router.get("/gates/{label}", response_model=GateStateOut)
async def get_gate(label: str, db: AsyncSession = Depends(get_db)):
    gate = await staging_service.get_gate(db, label)
    if not gate:
        raise HTTPException(status_code=404, detail=f"Gate {label} not found.")
    return gate


@router.post("/gates/{label}/clear", response_model=GateStateOut)
async def clear_gate(label: str, db: AsyncSession = Depends(get_db)):
    try:
        return await staging_service.clear_gate(db, label)
    except staging_service.StagingNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/gates/{label}/block", response_model=GateStateOut)
async def block_gate(
    label: str, notes: str | None = Query(None), db: AsyncSession = Depends(get_db)
):
    try:
        return await staging_service.block_gate(db, label, notes)
    except staging_service.StagingNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/is-adaptive-active")
async def is_adaptive_active(db: AsyncSession = Depends(get_db)):
    """Whether adaptive machinery (ABSF/CASS/ERME) should currently be running."""
    mode = await staging_service.get_current_mode(db)
    active = mode is not None and mode.current_mode == "ADAPTIVE"
    return {"adaptive_active": active, "current_mode": mode.current_mode if mode else None, "fallback": "Conventional Mode is the permanent floor"}
