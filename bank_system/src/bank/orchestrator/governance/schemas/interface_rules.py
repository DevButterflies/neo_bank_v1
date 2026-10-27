import uuid

from pydantic import BaseModel, ConfigDict, Field


class InterfaceRuleCreate(BaseModel):
    rule_number: str = Field(..., description="e.g. '6.7'")
    name: str
    description: str | None = None
    direction: str
    decides_who: str | None = None
    executes_who: str | None = None
    bypasses_pillar3: bool = False
    canon_section_ref: str | None = None
    notable_v34_change: str | None = None


class InterfaceFieldIn(BaseModel):
    field_name: str
    field_type: str | None = None
    cardinality: str = "1"
    direction: str = "SOURCE_TO_DEST"
    description: str | None = None
    is_pending: bool = False


class InterfaceFieldOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    interface_rule_id: uuid.UUID
    field_name: str
    field_type: str | None
    cardinality: str
    direction: str
    description: str | None
    is_pending: bool


class InterfaceRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    rule_number: str
    name: str
    description: str | None
    direction: str
    decides_who: str | None
    executes_who: str | None
    bypasses_pillar3: bool
    canon_section_ref: str | None
    notable_v34_change: str | None


class InterfaceRuleOutDetail(InterfaceRuleOut):
    fields: list[InterfaceFieldOut] = []


class InterfaceFlowCheck(BaseModel):
    source: str = Field(..., description="e.g. 'P2'")
    destination: str = Field(..., description="e.g. 'P4'")


class InterfaceFlowResult(BaseModel):
    rules: list[InterfaceRuleOut] = []
    bypasses_pillar3: bool = False
