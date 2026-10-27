from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from bank.orchestrator.governance.deps import get_db
from bank.orchestrator.governance.schemas.interface_rules import (
    InterfaceFlowCheck,
    InterfaceFlowResult,
    InterfaceRuleOut,
    InterfaceRuleOutDetail,
)
from bank.orchestrator.governance.services import interface_service

router = APIRouter(prefix="/interfaces", tags=["interface-rules"])


@router.get("", response_model=list[InterfaceRuleOutDetail])
async def list_interfaces(db: AsyncSession = Depends(get_db)):
    return await interface_service.list_interface_rules(db)


@router.get("/summary", response_model=list[InterfaceRuleOut])
async def interface_summary(db: AsyncSession = Depends(get_db)):
    return await interface_service.list_interface_rules(db)


@router.get("/{rule_number}", response_model=InterfaceRuleOutDetail)
async def get_interface(rule_number: str, db: AsyncSession = Depends(get_db)):
    rule = await interface_service.get_interface_rule(db, rule_number)
    if not rule:
        raise HTTPException(status_code=404, detail=f"Interface rule {rule_number} not found.")
    return rule


@router.post("/validate-flow", response_model=InterfaceFlowResult)
async def validate_flow(data: InterfaceFlowCheck, db: AsyncSession = Depends(get_db)):
    matched, bypasses = await interface_service.validate_flow(db, data.source, data.destination)
    return InterfaceFlowResult(rules=matched, bypasses_pillar3=bypasses)
