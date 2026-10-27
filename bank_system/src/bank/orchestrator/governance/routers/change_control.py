"""Change Control routes."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from bank.orchestrator.governance.deps import get_db
from bank.orchestrator.governance.schemas.change_control import (
    ChangeProposalCreate,
    ChangeProposalOut,
    ChangeProposalOutDetail,
    DependencyReviewCreate,
    DependencyReviewOut,
)
from bank.orchestrator.governance.services import change_control_service

router = APIRouter(prefix="/changes", tags=["change-control"])


@router.get("/proposals", response_model=list[ChangeProposalOut])
async def list_proposals(
    status: str | None = Query(None),
    change_type: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await change_control_service.list_proposals(db, status, change_type)


@router.post("/proposals", response_model=ChangeProposalOut, status_code=201)
async def create_proposal(
    data: ChangeProposalCreate, db: AsyncSession = Depends(get_db)
):
    return await change_control_service.create_proposal(db, data)


@router.get("/proposals/{proposal_id}", response_model=ChangeProposalOutDetail)
async def get_proposal(proposal_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    proposal = await change_control_service.get_proposal(db, proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found.")
    return proposal


@router.post(
    "/proposals/{proposal_id}/dependency-review",
    response_model=DependencyReviewOut,
)
async def submit_dependency_review(
    proposal_id: uuid.UUID, data: DependencyReviewCreate, db: AsyncSession = Depends(get_db)
):
    try:
        return await change_control_service.submit_dependency_review(db, proposal_id, data)
    except change_control_service.ChangeControlNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/proposals/{proposal_id}/ratify", response_model=ChangeProposalOut)
async def ratify_proposal(
    proposal_id: uuid.UUID,
    instrument_number: str | None = Query(None),
    resolution_ref: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await change_control_service.ratify_proposal(
            db, proposal_id, instrument_number, resolution_ref
        )
    except change_control_service.ChangeControlNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except change_control_service.ChangeControlConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/proposals/{proposal_id}/reject", response_model=ChangeProposalOut)
async def reject_proposal(proposal_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    try:
        return await change_control_service.reject_proposal(db, proposal_id)
    except change_control_service.ChangeControlNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
