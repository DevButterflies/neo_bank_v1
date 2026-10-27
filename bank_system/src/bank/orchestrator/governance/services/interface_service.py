"""Interface rules service."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bank.orchestrator.governance.models.interface_rules import InterfaceRule


class InterfaceNotFoundError(Exception):
    pass


async def list_interface_rules(db: AsyncSession) -> list[InterfaceRule]:
    result = await db.execute(
        select(InterfaceRule)
        .options(selectinload(InterfaceRule.fields))
        .order_by(InterfaceRule.rule_number)
    )
    return list(result.scalars().all())


async def get_interface_rule(
    db: AsyncSession, rule_number: str
) -> InterfaceRule | None:
    result = await db.execute(
        select(InterfaceRule)
        .options(selectinload(InterfaceRule.fields))
        .where(InterfaceRule.rule_number == rule_number)
        .limit(1)
    )
    return result.scalar_one_or_none()


async def validate_flow(db: AsyncSession, source: str, destination: str):
    """Given source/destination pillar, return matching interface rules and whether P3 is bypassed."""
    rules = await list_interface_rules(db)
    # Match rules whose direction string contains both source and destination tokens.
    source_tok = source.upper()
    dest_tok = destination.upper()
    matched = []
    bypasses = False
    for rule in rules:
        dir_upper = rule.direction.upper().replace("_", " ").replace("-", " ")
        if source_tok in dir_upper and dest_tok in dir_upper:
            matched.append(rule)
            if rule.bypasses_pillar3:
                bypasses = True
    return matched, bypasses
