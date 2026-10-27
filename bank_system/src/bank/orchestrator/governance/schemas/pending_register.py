import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PendingItemCreate(BaseModel):
    title: str
    description: str | None = None
    category: str = Field(
        default="GOVERNANCE",
        pattern="^(DATA_CONTRACT|INTERFACE|MECHANICS|GOVERNANCE|GATE_CRITERIA|DOCUMENTATION)$",
    )
    registered_in_canon: str | None = None
    scope_details: str | None = None
    priority: str = Field(default="MEDIUM", pattern="^(CRITICAL|HIGH|MEDIUM|LOW)$")
    assigned_to: str | None = None


class PendingItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    item_number: str
    title: str
    description: str | None
    category: str
    registered_in_canon: str | None
    scope_details: str | None
    status: str
    priority: str
    assigned_to: str | None
    registered_at: datetime
    resolved_at: datetime | None
    resolution_notes: str | None
    governance_reference: str | None


class PendingItemUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    category: str | None = None
    scope_details: str | None = None
    priority: str | None = None
    assigned_to: str | None = None
    status: str | None = Field(
        default=None, pattern="^(OPEN|IN_PROGRESS|RESOLVED|STRUCK)$"
    )


class PendingItemResolve(BaseModel):
    resolution_notes: str = Field(..., min_length=3, description="Required by do-not-resolve-in-code discipline")
    governance_reference: str | None = Field(
        default=None, description="e.g. 'RI-3' or governance ruling reference"
    )


class PendingSummary(BaseModel):
    total: int = 0
    open: int = 0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_priority: dict[str, int] = Field(default_factory=dict)
