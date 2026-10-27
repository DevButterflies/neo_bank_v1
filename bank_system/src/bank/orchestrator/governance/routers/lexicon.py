from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from bank.orchestrator.governance.deps import get_db
from bank.orchestrator.governance.schemas.lexicon import (
    LexiconCategoryOut,
    LexiconTermCreate,
    LexiconTermOut,
    LexiconTermUpdate,
    LexiconValidateRequest,
    LexiconValidateResult,
)
from bank.orchestrator.governance.services import lexicon_service

router = APIRouter(prefix="/lexicon", tags=["lexicon"])


@router.get("/categories", response_model=list[LexiconCategoryOut])
async def list_categories(db: AsyncSession = Depends(get_db)):
    return await lexicon_service.list_categories(db)


@router.get("/terms", response_model=list[LexiconTermOut])
async def list_terms(
    category_id: str | None = Query(None),
    model_scope: str | None = Query(None),
    search: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await lexicon_service.list_terms(db, category_id, model_scope, search)


@router.get("/terms/{term}", response_model=LexiconTermOut)
async def get_term(term: str, db: AsyncSession = Depends(get_db)):
    found = await lexicon_service.get_term(db, term)
    if not found:
        raise HTTPException(status_code=404, detail=f"Term '{term}' not found in Master Lexicon.")
    return found


@router.get("/renamed", response_model=list[LexiconTermOut])
async def list_renamed(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select
    from bank.orchestrator.governance.models.lexicon import LexiconTerm

    result = await db.execute(select(LexiconTerm).where(LexiconTerm.supersedes.isnot(None)))
    return list(result.scalars().all())


@router.post("/terms", response_model=LexiconTermOut, status_code=201)
async def create_term(data: LexiconTermCreate, db: AsyncSession = Depends(get_db)):
    try:
        return await lexicon_service.create_term(db, data)
    except lexicon_service.LexiconConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.put("/terms/{term}", response_model=LexiconTermOut)
async def update_term(
    term: str, data: LexiconTermUpdate, db: AsyncSession = Depends(get_db)
):
    try:
        return await lexicon_service.update_term(db, term, data)
    except lexicon_service.LexiconNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/validate", response_model=LexiconValidateResult)
async def validate_terms(
    data: LexiconValidateRequest, db: AsyncSession = Depends(get_db)
):
    return await lexicon_service.validate_terms(db, data)
