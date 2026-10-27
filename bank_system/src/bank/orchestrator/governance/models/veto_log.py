import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from bank.orchestrator.governance.database import Base


class VetoEvent(Base):
    __tablename__ = "veto_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    event_number: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)  # VE-001
    track: Mapped[int] = mapped_column(Integer, nullable=False)  # 1 or 2
    scope: Mapped[str] = mapped_column(String(64), nullable=False)  # facility|portfolio|pillar
    facility_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    pillar_4_signal: Mapped[str] = mapped_column(Text, nullable=True)
    p2_packet_action: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # WITHHELD|WITHDRAWN
    orchestrator_notified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    governance_review_status: Mapped[str] = mapped_column(
        String(64), nullable=False, default="OPEN"
    )  # OPEN|RESTART_AUTHORIZED|PACKET_REMAINS_WITHHELD
    restart_authorized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    restart_authorized_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
