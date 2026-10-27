import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CanonVersionCreate(BaseModel):
    version_number: str = Field(..., description="Canon version number, e.g. '3.4'")
    name: str
    change_summary: str | None = None
    lineage_notes: str | None = None
    status: str = Field(default="PENDING")


class CanonVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version_number: str
    name: str
    status: str
    ratified_at: datetime | None
    ratification_instrument: str | None
    is_current: bool
    change_summary: str | None
    lineage_notes: str | None
    created_at: datetime


class CanonVersionOutDetail(CanonVersionOut):
    ratification_instruments: list["RatificationInstrumentOut"] = []


class CanonVersionRatify(BaseModel):
    instrument_number: str = Field(..., description="e.g. 'RI-4'")
    resolution_ref: str | None = None
    description: str | None = None
    ratified_by: str = "Governance Committee"


class RatificationInstrumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    canon_version_id: uuid.UUID
    instrument_number: str
    resolution_ref: str | None
    description: str | None
    ratified_at: datetime
