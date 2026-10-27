import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bank.orchestrator.governance.database import Base


class ChangeProposal(Base):
    __tablename__ = "change_proposals"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    proposal_number: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)  # CP-001
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    change_type: Mapped[str] = mapped_column(
        String(64), nullable=False, default="STRUCTURAL"
    )  # STRUCTURAL|INTERFACE|TIER|LEXICON|MIGRATION_G2S|CALIBRATION
    proposed_by: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="SUBMITTED"
    )  # SUBMITTED|UNDER_REVIEW|DEPENDENCY_REVIEW|RATIFIED|REJECTED
    canon_version_target: Mapped[str | None] = mapped_column(String(32), nullable=True)
    requires_dependency_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    requires_g2s_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    dependency_reviews: Mapped[list["DependencyReview"]] = relationship(
        back_populates="proposal", cascade="all, delete-orphan"
    )
    ratification_votes: Mapped[list["RatificationVote"]] = relationship(
        back_populates="proposal", cascade="all, delete-orphan"
    )


class DependencyReview(Base):
    __tablename__ = "dependency_reviews"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    proposal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("change_proposals.id", ondelete="CASCADE"), nullable=False
    )
    pillar_number: Mapped[int] = mapped_column(default=0, nullable=False)
    review_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="PENDING"
    )  # PENDING|APPROVED|BLOCKED|NOT_APPLICABLE
    reviewer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    proposal: Mapped[ChangeProposal] = relationship(back_populates="dependency_reviews")


class RatificationVote(Base):
    __tablename__ = "ratification_votes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    proposal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("change_proposals.id", ondelete="CASCADE"), nullable=False
    )
    instrument_number: Mapped[str | None] = mapped_column(String(32), nullable=True)  # RI-N
    resolution_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    vote: Mapped[str] = mapped_column(String(16), nullable=False)  # RATIFIED|REJECTED
    voted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    voted_by: Mapped[str] = mapped_column(String(128), nullable=False, default="Governance Committee")

    proposal: Mapped[ChangeProposal] = relationship(back_populates="ratification_votes")
