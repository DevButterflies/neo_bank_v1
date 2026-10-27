import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChangeProposalCreate(BaseModel):
    title: str
    description: str | None = None
    change_type: str = Field(
        default="STRUCTURAL",
        pattern="^(STRUCTURAL|INTERFACE|TIER|LEXICON|MIGRATION_G2S|CALIBRATION)$",
    )
    proposed_by: str
    canon_version_target: str | None = None
    requires_dependency_review: bool = False
    requires_g2s_review: bool = False


class ChangeProposalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    proposal_number: str
    title: str
    description: str | None
    change_type: str
    proposed_by: str
    status: str
    canon_version_target: str | None
    requires_dependency_review: bool
    requires_g2s_review: bool
    submitted_at: datetime
    resolved_at: datetime | None


class ChangeProposalOutDetail(ChangeProposalOut):
    dependency_reviews: list["DependencyReviewOut"] = []
    ratification_votes: list["RatificationVoteOut"] = []


class DependencyReviewCreate(BaseModel):
    pillar_number: int = Field(..., ge=1, le=5)
    review_status: str = Field(
        default="PENDING", pattern="^(PENDING|APPROVED|BLOCKED|NOT_APPLICABLE)$"
    )
    reviewer_notes: str | None = None


class DependencyReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    proposal_id: uuid.UUID
    pillar_number: int
    review_status: str
    reviewer_notes: str | None
    reviewed_at: datetime | None


class RatificationVoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    proposal_id: uuid.UUID
    instrument_number: str | None
    resolution_ref: str | None
    vote: str
    voted_at: datetime
    voted_by: str
