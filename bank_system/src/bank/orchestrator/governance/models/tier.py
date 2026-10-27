import uuid

from sqlalchemy import ForeignKey, Integer, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bank.orchestrator.governance.database import Base


class TierDefinition(Base):
    __tablename__ = "tier_definitions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tier_label: Mapped[str] = mapped_column(String(8), nullable=False, unique=True)  # "A", "B", "C", "D"
    tier_name: Mapped[str] = mapped_column(String(255), nullable=False)
    model_scope: Mapped[str] = mapped_column(String(16), nullable=False, default="G")  # G|S
    description: Mapped[str] = mapped_column(Text, nullable=True)
    insurance_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    insurance_status_authority: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    canon_section_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)

    protection_rules_out: Mapped[list["TierProtectionRule"]] = relationship(
        foreign_keys="TierProtectionRule.source_tier_id", back_populates="source_tier"
    )
    protection_rules_in: Mapped[list["TierProtectionRule"]] = relationship(
        foreign_keys="TierProtectionRule.target_tier_id", back_populates="target_tier"
    )


class TierProtectionRule(Base):
    __tablename__ = "tier_protection_rules"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_tier_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tier_definitions.id", ondelete="CASCADE"), nullable=False
    )
    target_tier_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tier_definitions.id", ondelete="CASCADE"), nullable=False
    )
    direction: Mapped[str] = mapped_column(String(32), nullable=False)  # PROTECTS|ABSORBS_LOSS_FROM
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    source_tier: Mapped[TierDefinition] = relationship(
        foreign_keys=[source_tier_id], back_populates="protection_rules_out"
    )
    target_tier: Mapped[TierDefinition] = relationship(
        foreign_keys=[target_tier_id], back_populates="protection_rules_in"
    )


class PillarBoundary(Base):
    __tablename__ = "pillar_boundaries"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    pillar_number: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)  # 1-5
    pillar_name: Mapped[str] = mapped_column(String(255), nullable=False)
    produces: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    consumes: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    decides: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    must_not_do: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    canon_section_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
