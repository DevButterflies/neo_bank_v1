from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from bank.orchestrator.governance.deps import get_db
from bank.orchestrator.governance.schemas.canon import (
    CanonVersionCreate,
    CanonVersionOut,
    CanonVersionOutDetail,
    CanonVersionRatify,
    RatificationInstrumentOut,
)
from bank.orchestrator.governance.services import canon_service

router = APIRouter(prefix="/canon", tags=["canon"])


@router.get("/current", response_model=CanonVersionOut)
async def get_current_canon(db: AsyncSession = Depends(get_db)):
    canon = await canon_service.get_current_canon(db)
    if not canon:
        raise HTTPException(status_code=404, detail="No current canon version set. Seed the registry first.")
    return canon


@router.get("/versions", response_model=list[CanonVersionOut])
async def list_versions(db: AsyncSession = Depends(get_db)):
    return await canon_service.list_canon_versions(db)


@router.get("/versions/{version}", response_model=CanonVersionOutDetail)
async def get_version(version: str, db: AsyncSession = Depends(get_db)):
    canon = await canon_service.get_canon_by_version(db, version)
    if not canon:
        raise HTTPException(status_code=404, detail=f"Canon version {version} not found.")
    instruments = await canon_service.get_ratifications(db, canon.id)
    from bank.orchestrator.governance.schemas.canon import RatificationInstrumentOut

    return CanonVersionOutDetail(
        **canon.__dict__,
        ratification_instruments=[
            RatificationInstrumentOut.model_validate(i) for i in instruments
        ],
    )


@router.get("/lineage", response_model=list[CanonVersionOut])
async def get_lineage(db: AsyncSession = Depends(get_db)):
    return await canon_service.list_canon_versions(db)


@router.post("/versions", response_model=CanonVersionOut, status_code=201)
async def create_version(
    data: CanonVersionCreate, db: AsyncSession = Depends(get_db)
):
    try:
        return await canon_service.create_canon_version(db, data)
    except canon_service.CanonConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/versions/{version}/ratify", response_model=CanonVersionOut)
async def ratify_version(
    version: str, data: CanonVersionRatify, db: AsyncSession = Depends(get_db)
):
    try:
        return await canon_service.ratify_canon_version(db, version, data)
    except canon_service.CanonNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except canon_service.CanonConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/versions/{version}/supersede", response_model=CanonVersionOut)
async def supersede_version(version: str, db: AsyncSession = Depends(get_db)):
    try:
        return await canon_service.supersede_canon_version(db, version)
    except canon_service.CanonNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
