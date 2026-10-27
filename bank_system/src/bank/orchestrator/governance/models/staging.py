import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from bank.orchestrator.governance.database import Base


class ModeState(Base):
    __tablename__ = "mode_state"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    current_mode: Mapped[str] = mapped_column(String(32), nullable=False)  # CONVENTIONAL|ADAPTIVE
    fallback_guarantee: Mapped[str] = mapped_column(
        Text, nullable=False, default="Conventional Mode is the permanent floor of the system"
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    changed_by: Mapped[str] = mapped_column(String(128), nullable=False, default="Governance Committee")
    change_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)


class StageState(Base):
    __tablename__ = "stage_state"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    current_stage: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 0|1|2|3
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    changed_by: Mapped[str] = mapped_column(String(128), nullable=False, default="Governance Committee")


class GateState(Base):
    __tablename__ = "gate_state"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    gate_label: Mapped[str] = mapped_column(String(16), nullable=False, unique=True)  # G0|G1|G2|G3
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")  # PENDING|CLEARED|BLOCKED
    criteria: Mapped[str | None] = mapped_column(Text, nullable=True)
    cleared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cleared_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
