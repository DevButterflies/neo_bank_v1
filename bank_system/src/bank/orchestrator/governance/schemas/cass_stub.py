import uuid

from pydantic import BaseModel, ConfigDict, Field


class CassStubMetadataIn(BaseModel):
    version: str = "1.0"
    issued_by: str = "Orchestrator"
    scope: str = "contract shape only — never signal derivation or consumption logic"
    source_pillar: str = "P2"
    dest_pillar: str = "P4"
    refresh_cadence: str | None = None
    failure_semantics: str | None = None


class CassStubFieldIn(BaseModel):
    field_name: str
    field_type: str | None = None
    cardinality: str = "1"
    description: str | None = None
    is_derived: bool = False
    is_consumed: bool = False


class CassStubFieldOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    stub_metadata_id: uuid.UUID
    field_name: str
    field_type: str | None
    cardinality: str
    description: str | None
    is_derived: bool
    is_consumed: bool


class CassStubMetadataOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version: str
    issued_by: str
    scope: str
    source_pillar: str
    dest_pillar: str
    refresh_cadence: str | None
    failure_semantics: str | None
    fields: list[CassStubFieldOut] = []
