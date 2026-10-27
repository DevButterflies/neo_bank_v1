"""Master Lexicon service."""

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bank.orchestrator.governance.models.lexicon import LexiconCategory, LexiconTerm
from bank.orchestrator.governance.schemas.lexicon import (
    LexiconTermCreate,
    LexiconTermUpdate,
    LexiconValidateRequest,
    LexiconValidateResult,
)


class LexiconConflictError(Exception):
    pass


class LexiconNotFoundError(Exception):
    pass


async def list_categories(db: AsyncSession) -> list[LexiconCategory]:
    result = await db.execute(
        select(LexiconCategory).order_by(LexiconCategory.sort_order)
    )
    return list(result.scalars().all())


async def list_terms(
    db: AsyncSession,
    category_id=None,
    model_scope=None,
    search: str | None = None,
) -> list[LexiconTerm]:
    stmt = select(LexiconTerm)
    if category_id:
        stmt = stmt.where(LexiconTerm.category_id == category_id)
    if model_scope:
        stmt = stmt.where(LexiconTerm.model_scope == model_scope)
    if search:
        stmt = stmt.where(
            or_(
                LexiconTerm.term.ilike(f"%{search}%"),
                LexiconTerm.definition.ilike(f"%{search}%"),
            )
        )
    stmt = stmt.order_by(LexiconTerm.term)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_term(db: AsyncSession, term: str) -> LexiconTerm | None:
    result = await db.execute(
        select(LexiconTerm).where(LexiconTerm.term.ilike(term)).limit(1)
    )
    return result.scalar_one_or_none()


async def create_term(db: AsyncSession, data: LexiconTermCreate) -> LexiconTerm:
    existing = await get_term(db, data.term)
    if existing:
        raise LexiconConflictError(f"Term '{data.term}' already exists in the Master Lexicon.")
    term = LexiconTerm(**data.model_dump())
    db.add(term)
    await db.commit()
    await db.refresh(term)
    return term


async def update_term(
    db: AsyncSession, term_name: str, data: LexiconTermUpdate
) -> LexiconTerm:
    term = await get_term(db, term_name)
    if not term:
        raise LexiconNotFoundError(f"Term '{term_name}' not found.")
    updates = data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(term, field, value)
    await db.commit()
    await db.refresh(term)
    return term


async def validate_terms(
    db: AsyncSession, data: LexiconValidateRequest
) -> LexiconValidateResult:
    """Given a list of terms, classify each as valid / invalid / renamed."""
    result = LexiconValidateResult()
    for term in data.terms:
        found = await get_term(db, term)
        if found:
            result.valid.append(found.term)
        else:
            # Check if this term is the OLD name of a renamed term.
            renamed_result = await db.execute(
                select(LexiconTerm).where(LexiconTerm.supersedes.ilike(term)).limit(1)
            )
            renamed = renamed_result.scalar_one_or_none()
            if renamed:
                result.renamed[term] = renamed.term
            else:
                result.invalid.append(term)
    return result
