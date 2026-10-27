import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bank.orchestrator.governance.database import Base


class CassStubMetadata(Base):
    __tablename__ = "cass_stub_metadata"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    issued_by: Mapped[str] = mapped_column(String(64), nullable=False, default="Orchestrator")
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    source_pillar: Mapped[str] = mapped_column(String(16), nullable=False, default="P2")
    dest_pillar: Mapped[str] = mapped_column(String(16), nullable=False, default="P4")
    refresh_cadence: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_semantics: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    fields: Mapped[list["CassStubField"]] = relationship(
        back_populates="stub", cascade="all, delete-orphan"
    )


class CassStubField(Base):
    __tablename__ = "cass_stub_fields"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    stub_metadata_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cass_stub_metadata.id", ondelete="CASCADE"), nullable=False
    )
    field_name: Mapped[str] = mapped_column(String(255), nullable=False)
    field_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cardinality: Mapped[str] = mapped_column(String(16), nullable=False, default="1")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_derived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_consumed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    stub: Mapped[CassStubMetadata] = relationship(back_populates="fields")
