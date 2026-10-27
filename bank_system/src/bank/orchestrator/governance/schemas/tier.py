import uuid

from pydantic import BaseModel, ConfigDict, Field


class TierDefinitionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tier_label: str
    tier_name: str
    model_scope: str
    description: str | None
    insurance_status: str | None
    insurance_status_authority: str | None
    sort_order: int
    canon_section_ref: str | None


class TierProtectionRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_tier_id: uuid.UUID
    target_tier_id: uuid.UUID
    direction: str
    description: str | None


class PillarBoundaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    pillar_number: int
    pillar_name: str
    produces: list
    consumes: list
    decides: list
    must_not_do: list
    canon_section_ref: str | None


class PillarPerimeterCheck(BaseModel):
    pillar_number: int = Field(..., ge=1, le=5)
    action: str = Field(..., description="A textual description of the proposed action")


class PillarPerimeterCheckResult(BaseModel):
    allowed: bool
    reason: str
    violated_rule: str | None = None
