"""Pydantic I/O schemas for the P1 candidate API.

``CandidateCreate`` is the borrower intake form the demo front-end posts.
``PaymentBehavior`` mirrors the exact shape the demo_3 profiles carried
(repayments with interest/principal per month, optional delinquent/default
months, a recovered amount) so seed candidates and auto-generated candidates
share one schema.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, computed_field, field_validator, model_validator


class RepaymentRow(BaseModel):
    """One scheduled instalment; ``month`` is 1-based from disbursement."""

    interest: float = Field(ge=0)
    principal: float = Field(ge=0)
    month: int = Field(ge=1)


Outcome = Literal["paid", "default", "delinquent_cured"]


class PaymentBehavior(BaseModel):
    """The payment path a facility follows once disbursed (drives ``/tick``)."""

    outcome: Outcome = "paid"
    facility_amount: float = Field(ge=1)
    disbursed: float = Field(ge=0)
    currency: str = "USD"
    tenure_months: int = Field(default=12, ge=1)
    repayments: list[RepaymentRow] = Field(default_factory=list)
    delinquent_month: int | None = Field(default=None, ge=1)
    default_month: int | None = Field(default=None, ge=1)
    recovered_amount: float = Field(default=0.0, ge=0)
    interest_rate_bps: int = Field(default=1000, ge=0)


class CandidateCreate(BaseModel):
    """Borrower intake form."""

    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    name_ar: str | None = None
    gender: Literal["male", "female"] = "male"
    age: int = Field(default=0, ge=18, le=100)
    national_id: str | None = None
    phone: str | None = None
    city: str = "Muscat"

    employer_name: str | None = None
    employer_type: Literal["government", "military", "private", "self_employed"] | None = None
    employment_years: float = Field(default=1.0, ge=0)
    employer_start_date: str | None = None
    job_title: str | None = None
    monthly_salary: float = Field(ge=0)

    product: str = "auto_loan"
    requested_amount: float = Field(ge=1)
    requested_tenure_months: int = Field(default=12, ge=1, le=60)

    # Optional override of the auto-generated payment behaviour.
    payment_behavior: PaymentBehavior | None = None
    # Convenience: force the auto-generator's outcome instead of full behavior.
    outcome_override: Outcome | None = None

    @field_validator("monthly_salary")
    @classmethod
    def _salary_positive(cls, v: float) -> float:
        return v or 0.0


class CandidateImport(CandidateCreate):
    """Ingest of an exported candidate JSON (see ``export_candidates.py``).

    Appends the exported columns that are NOT part of the intake form so a
    previously-disbursed candidate can be restored with its full application
    payload, sim state and seed profile.
    """

    seed_profile: str | None = None
    application_json: dict | None = None
    sim_state: dict | None = None


class CandidateUpdate(BaseModel):
    """Partial update of editable intake fields (not lifecycle fields)."""

    phone: str | None = None
    city: str | None = None
    employer_name: str | None = None
    job_title: str | None = None


class ApprovalDecision(BaseModel):
    """The manual officer gate — ALWAYS required (MANUAL_APPROVAL_ALWAYS)."""

    approve: bool = True
    officer_id: str = "OFFICER-1"
    officer_name: str | None = None
    note: str | None = None


class DisbursementRequest(BaseModel):
    amount: float | None = Field(default=None, gt=0)
    currency: str = "USD"


class CandidateRead(BaseModel):
    """API representation of a candidate row."""

    model_config = {"from_attributes": True}

    id: str
    seed_profile: str | None
    first_name: str
    last_name: str
    name_ar: str | None
    gender: str
    age: int
    national_id: str | None
    phone: str | None
    city: str
    employer_name: str | None
    employer_type: str | None
    employment_years: float
    job_title: str | None
    monthly_salary: float
    product: str
    requested_amount: float
    requested_tenure_months: int

    status: str
    submitted_at: datetime | None
    scored_at: datetime | None
    approved_at: datetime | None
    originated_at: datetime | None
    disbursed_at: datetime | None

    application_id: str | None
    facility_id: str | None
    p2_brr: int | None
    p2_pd: float | None
    p2_zone: str | None
    p2_packet_status: str | None

    payment_behavior: dict | None
    sim_state: dict | None
    created_at: datetime
    updated_at: datetime
    approval_note: str | None
    approved_by: str | None

    @computed_field
    @property
    def display_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


# ---- response envelopes (Swagger documentation shapes) -----------------------
# These wrap the dict responses the flow/service layer returns. ``extra`` is
# left permissive so documenting the envelope never alters the payload.


class CandidateEnvelope(BaseModel):
    candidate: CandidateRead
    payment_behavior: dict | None = None


class CandidateListOut(BaseModel):
    candidates: list[CandidateRead]


class DataFileInfo(BaseModel):
    filename: str
    name: str = "?"
    seed_profile: str | None = None
    status: str = "new"
    size_bytes: int = 0


class DataFileListOut(BaseModel):
    files: list[DataFileInfo]


class FlowResultOut(BaseModel):
    """Result of submit / approve / disburse — scoring and lifecycle fields."""

    model_config = {"extra": "allow"}

    status: str | None = None
    candidate_id: str | None = None
    facility_id: str | None = None
    packet_id: str | None = None
    approved: bool | None = None
    amount: float | None = None
    currency: str | None = None
    brr: int | None = None
    pd: float | None = None
    zone: str | None = None


class SeedOut(BaseModel):
    seeded: int


class ResetOut(BaseModel):
    status: str
    state: dict


class TickOut(BaseModel):
    tick: dict
    state: dict