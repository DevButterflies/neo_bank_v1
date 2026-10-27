import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bank.orchestrator.governance.database import Base


class CanonVersion(Base):
    __tablename__ = "canon_versions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    version_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)  # RATIFIED|PENDING|SUPERSEDED
    ratified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ratification_instrument: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_current: Mapped[bool] = mapped_column(default=False, nullable=False)
    change_summary: Mapped[str] = mapped_column(Text, nullable=True)
    lineage_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    ratification_instruments: Mapped[list["RatificationInstrument"]] = relationship(
        back_populates="canon_version"
    )


class RatificationInstrument(Base):
    __tablename__ = "ratification_instruments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    canon_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("canon_versions.id", ondelete="CASCADE"), nullable=False
    )
    instrument_number: Mapped[str] = mapped_column(String(32), nullable=False)  # "RI-1"
    resolution_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    ratified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    canon_version: Mapped[CanonVersion] = relationship(back_populates="ratification_instruments")
