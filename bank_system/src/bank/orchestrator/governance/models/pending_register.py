import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from bank.orchestrator.governance.database import Base


class PendingItem(Base):
    __tablename__ = "pending_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    item_number: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)  # P-001
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(
        String(64), nullable=False, default="GOVERNANCE"
    )  # DATA_CONTRACT|INTERFACE|MECHANICS|GOVERNANCE|GATE_CRITERIA|DOCUMENTATION
    registered_in_canon: Mapped[str | None] = mapped_column(String(64), nullable=True)
    scope_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="OPEN"
    )  # OPEN|IN_PROGRESS|RESOLVED|STRUCK
    priority: Mapped[str] = mapped_column(
        String(16), nullable=False, default="MEDIUM"
    )  # CRITICAL|HIGH|MEDIUM|LOW
    assigned_to: Mapped[str | None] = mapped_column(String(128), nullable=True)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    governance_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
