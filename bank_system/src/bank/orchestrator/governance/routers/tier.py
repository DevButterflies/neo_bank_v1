from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from bank.orchestrator.governance.deps import get_db
from bank.orchestrator.governance.schemas.tier import (
    PillarBoundaryOut,
    PillarPerimeterCheck,
    PillarPerimeterCheckResult,
    TierDefinitionOut,
    TierProtectionRuleOut,
)
from bank.orchestrator.governance.services import tier_service

router = APIRouter(tags=["tiers-and-pillars"])


class InsuranceStatusUpdate(BaseModel):
    status: str = Field(..., description="Tier A insurance status (sole locus rule)")


@router.get("/tiers", response_model=list[TierDefinitionOut])
async def list_tiers(db: AsyncSession = Depends(get_db)):
    return await tier_service.list_tiers(db)


@router.get("/tiers/protection-rules", response_model=list[TierProtectionRuleOut])
async def list_protection_rules(db: AsyncSession = Depends(get_db)):
    return await tier_service.list_protection_rules(db)


@router.get("/tiers/{label}", response_model=TierDefinitionOut)
async def get_tier(label: str, db: AsyncSession = Depends(get_db)):
    tier = await tier_service.get_tier(db, label)
    if not tier:
        raise HTTPException(status_code=404, detail=f"Tier {label} not found.")
    return tier


@router.get("/tiers/{label}/insurance-status", response_model=TierDefinitionOut)
async def get_insurance_status(label: str, db: AsyncSession = Depends(get_db)):
    try:
        return await tier_service.get_tier_insurance_status(db, label)
    except tier_service.TierNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/tiers/{label}/insurance-status", response_model=TierDefinitionOut)
async def set_insurance_status(
    label: str, data: InsuranceStatusUpdate, db: AsyncSession = Depends(get_db)
):
    """§4.6 'sole locus' rule: Tier A insurance status resolves ONLY here."""
    try:
        return await tier_service.set_tier_insurance_status(db, label, data.status)
    except tier_service.TierNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/pillars", response_model=list[PillarBoundaryOut])
async def list_pillars(db: AsyncSession = Depends(get_db)):
    return await tier_service.list_pillars(db)


@router.get("/pillars/{number}", response_model=PillarBoundaryOut)
async def get_pillar(number: int, db: AsyncSession = Depends(get_db)):
    pillar = await tier_service.get_pillar(db, number)
    if not pillar:
        raise HTTPException(status_code=404, detail=f"Pillar {number} not found.")
    return pillar


@router.post("/pillars/{number}/check-perimeter", response_model=PillarPerimeterCheckResult)
async def check_perimeter(
    number: int, data: PillarPerimeterCheck, db: AsyncSession = Depends(get_db)
):
    """Check whether a proposed action is within a pillar's perimeter."""
    pillar = await tier_service.get_pillar(db, number)
    if not pillar:
        raise HTTPException(status_code=404, detail=f"Pillar {number} not found.")

    # Stopwords excluded from keyword matching to avoid false positives on
    # words like "a", "on", "the" appearing in any action description.
    STOPWORDS = {
        "a", "an", "the", "on", "in", "of", "for", "to", "and", "or", "is",
        "are", "not", "no", "its", "it", "any", "by", "from", "with", "this",
        "that", "as", "at", "per", "be", "being", "than",
    }

    action_lower = data.action.lower()
    for rule in pillar.must_not_do:
        rule_lower = rule.lower()
        # Direct phrase containment is the strongest signal.
        if rule_lower in action_lower:
            return PillarPerimeterCheckResult(
                allowed=False,
                reason=f"Action violates Pillar {number} perimeter rule: '{rule}'",
                violated_rule=rule,
            )
        # Otherwise, require at least two substantive non-stopword keywords from
        # the rule to appear in the action (allowing singular/plural variants) —
        # reduces false positives while catching e.g. "credit decision(s)".
        keywords = [
            w for w in rule_lower.split() if w not in STOPWORDS and len(w) > 2
        ]

        def word_variants(word: str) -> list[str]:
            variants = {word}
            if word.endswith("s"):
                variants.add(word[:-1])
            else:
                variants.add(word + "s")
            return list(variants)

        def keyword_matches(word: str) -> bool:
            return any(
                v in action_lower for v in word_variants(word)
            )

        matched = [w for w in keywords if keyword_matches(w)]
        if len(keywords) >= 2 and len(matched) >= 2:
            return PillarPerimeterCheckResult(
                allowed=False,
                reason=f"Action appears to violate Pillar {number} perimeter rule: '{rule}'",
                violated_rule=rule,
            )
    return PillarPerimeterCheckResult(
        allowed=True,
        reason=f"Action is within Pillar {number} perimeter.",
    )
