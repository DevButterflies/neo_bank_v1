"""Pillar 1 candidate persistence model.

P1 is the MSME engagement & data-acquisition pillar: it ingests a borrower
intake form, stores the candidate, and (in this demo build) auto-generates a
deterministic payment behaviour used to drive the loan-lifecycle simulation.

The ``Candidate`` row lives in the orchestrator's one governance SQLite file
(same ``/data/orchestrator.db`` the P3/P4 KvStore and governance registries
share) on the shared ``Base`` metadata, so ``create_all`` in
:func:`bank.orchestrator.governance.database.init_models` creates the table.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from bank.orchestrator.governance.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Candidate(Base):
    """A P1 borrower intake with its lifecycle + simulation state.

    Identifiers flow end-to-end as ``candidate_id`` -> ``application_id``
    (P2) -> ``facility_id`` (P3) -> ``facility_ref`` (P4) via
    :mod:`bank.pillars.p1.flow`.
    """

    __tablename__ = "p1_candidates"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    seed_profile: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # -- Borrower intake form -------------------------------------------
    first_name: Mapped[str] = mapped_column(String(80), nullable=False)
    last_name: Mapped[str] = mapped_column(String(80), nullable=False)
    name_ar: Mapped[str | None] = mapped_column(String(120), nullable=True)
    gender: Mapped[str] = mapped_column(String(16), default="male")
    age: Mapped[int] = mapped_column(Integer, default=0)
    national_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    city: Mapped[str] = mapped_column(String(80), default="Muscat")

    employer_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    employer_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    employment_years: Mapped[float] = mapped_column(Float, default=1.0)
    employer_start_date: Mapped[str | None] = mapped_column(String(16), nullable=True)
    job_title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    monthly_salary: Mapped[float] = mapped_column(Float, default=0.0)

    product: Mapped[str] = mapped_column(String(32), default="auto_loan")
    requested_amount: Mapped[float] = mapped_column(Float, default=0.0)
    requested_tenure_months: Mapped[int] = mapped_column(Integer, default=12)

    # -- Lifecycle ------------------------------------------------------
    status: Mapped[str] = mapped_column(
        String(32), default="new", index=True
    )  # new|scored|approved|originated|disbursed|closed|defaulted
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    originated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    disbursed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # -- End-to-end identifiers -----------------------------------------
    application_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    facility_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # -- P2 scoring outputs (informational copy) ------------------------
    p2_brr: Mapped[int | None] = mapped_column(Integer, nullable=True)
    p2_pd: Mapped[float | None] = mapped_column(Float, nullable=True)
    p2_lgd: Mapped[float | None] = mapped_column(Float, nullable=True)
    p2_ead: Mapped[float | None] = mapped_column(Float, nullable=True)
    p2_el: Mapped[float | None] = mapped_column(Float, nullable=True)
    p2_zone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    p2_packet_status: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # -- Carried payloads -----------------------------------------------
    # Serialized BorrowerApplication handed to Pillar 2 at submit time.
    application_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Serialized PaymentBehavior driving the tick simulation.
    payment_behavior: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Simulation progress ({current_month, payments_made, defaulted, ...}).
    sim_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # -- Audit timestamps -----------------------------------------------
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )
    approval_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(128), nullable=True)

    @property
    def display_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def risk_rating(self) -> int | None:
        return self.p2_brr