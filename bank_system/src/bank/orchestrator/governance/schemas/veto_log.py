import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class VetoEventCreate(BaseModel):
    track: int = Field(..., ge=1, le=2)
    scope: str = Field(default="facility", pattern="^(facility|portfolio|pillar)$")
    facility_id: str | None = None
    pillar_4_signal: str | None = None
    p2_packet_action: str = Field(
        ..., pattern="^(WITHHELD|WITHDRAWN)$"
    )
    notes: str | None = None


class VetoEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_number: str
    track: int
    scope: str
    facility_id: str | None
    pillar_4_signal: str | None
    p2_packet_action: str
    orchestrator_notified_at: datetime
    governance_review_status: str
    restart_authorized_at: datetime | None
    restart_authorized_by: str | None
    notes: str | None


class VetoEventResolve(BaseModel):
    decision: str = Field(
        ..., pattern="^(RESTART_AUTHORIZED|PACKET_REMAINS_WITHHELD)$"
    )
    authorized_by: str = "Governance Committee"
    notes: str | None = None
