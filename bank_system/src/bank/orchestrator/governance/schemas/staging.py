import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ModeStateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    current_mode: str
    fallback_guarantee: str
    changed_at: datetime
    changed_by: str
    change_rationale: str | None


class ModeChangeIn(BaseModel):
    new_mode: str = Field(..., pattern="^(CONVENTIONAL|ADAPTIVE)$")
    changed_by: str = "Governance Committee"
    change_rationale: str | None = None


class StageStateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    current_stage: int
    changed_at: datetime
    changed_by: str


class GateStateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    gate_label: str
    status: str
    criteria: str | None
    cleared_at: datetime | None
    cleared_by: str | None
    notes: str | None
