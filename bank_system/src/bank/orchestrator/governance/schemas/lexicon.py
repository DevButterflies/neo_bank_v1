import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LexiconCategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    annex_ref: str
    description: str | None
    sort_order: int


class LexiconTermCreate(BaseModel):
    term: str = Field(..., description="The locked term name")
    category_id: uuid.UUID
    abbreviation: str | None = None
    definition: str
    model_scope: str = "NEUTRAL"
    canon_section_ref: str | None = None
    is_new_in_v34: bool = False
    supersedes: str | None = None


class LexiconTermOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category_id: uuid.UUID
    term: str
    abbreviation: str | None
    definition: str
    model_scope: str
    canon_section_ref: str | None
    is_new_in_v34: bool
    supersedes: str | None
    created_at: datetime
    updated_at: datetime


class LexiconTermUpdate(BaseModel):
    definition: str | None = None
    model_scope: str | None = None
    abbreviation: str | None = None
    is_new_in_v34: bool | None = None
    supersedes: str | None = None


class LexiconValidateRequest(BaseModel):
    terms: list[str] = Field(..., description="List of terms to validate against the Master Lexicon")


class LexiconValidateResult(BaseModel):
    valid: list[str] = []
    invalid: list[str] = []
    renamed: dict[str, str] = Field(
        default_factory=dict, description="old term -> new locked term"
    )
