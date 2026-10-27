import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bank.orchestrator.governance.database import Base


class InterfaceRule(Base):
    __tablename__ = "interface_rules"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    rule_number: Mapped[str] = mapped_column(String(16), nullable=False, unique=True)  # "6.1"..."6.7"
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    direction: Mapped[str] = mapped_column(String(64), nullable=False)
    decides_who: Mapped[str | None] = mapped_column(Text, nullable=True)
    executes_who: Mapped[str | None] = mapped_column(Text, nullable=True)
    bypasses_pillar3: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    canon_section_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notable_v34_change: Mapped[str | None] = mapped_column(Text, nullable=True)

    fields: Mapped[list["InterfaceField"]] = relationship(
        back_populates="interface_rule", cascade="all, delete-orphan"
    )


class InterfaceField(Base):
    __tablename__ = "interface_fields"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    interface_rule_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("interface_rules.id", ondelete="CASCADE"), nullable=False
    )
    field_name: Mapped[str] = mapped_column(String(255), nullable=False)
    field_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cardinality: Mapped[str] = mapped_column(String(16), nullable=False, default="1")
    direction: Mapped[str] = mapped_column(String(32), nullable=False)  # SOURCE_TO_DEST|DEST_TO_SOURCE
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_pending: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    interface_rule: Mapped[InterfaceRule] = relationship(back_populates="fields")
