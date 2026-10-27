from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from bank.orchestrator.governance.deps import get_db
from bank.orchestrator.governance.schemas.cass_stub import (
    CassStubMetadataIn,
    CassStubMetadataOut,
)
from bank.orchestrator.governance.services import cass_service

router = APIRouter(prefix="/cass-stub", tags=["cass-stub"])


@router.get("", response_model=CassStubMetadataOut)
async def get_stub(db: AsyncSession = Depends(get_db)):
    stub = await cass_service.get_current_stub(db)
    if not stub:
        raise HTTPException(status_code=404, detail="No CASS interface stub registered yet.")
    return stub


@router.put("", response_model=CassStubMetadataOut)
async def update_stub(data: CassStubMetadataIn, db: AsyncSession = Depends(get_db)):
    return await cass_service.create_or_update_stub(db, data)


@router.get("/fields", response_model=CassStubMetadataOut)
async def get_stub_fields(db: AsyncSession = Depends(get_db)):
    stub = await cass_service.get_current_stub(db)
    if not stub:
        raise HTTPException(status_code=404, detail="No CASS interface stub registered yet.")
    return stub


@router.get("/scope", response_model=CassStubMetadataOut)
async def get_stub_scope(db: AsyncSession = Depends(get_db)):
    stub = await cass_service.get_current_stub(db)
    if not stub:
        raise HTTPException(status_code=404, detail="No CASS interface stub registered yet.")
    return stub
