import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bank.orchestrator.governance.database import Base


class LexiconCategory(Base):
    __tablename__ = "lexicon_categories"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    annex_ref: Mapped[str] = mapped_column(String(32), nullable=False)  # "A.1", "A.2", ...
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False)

    terms: Mapped[list["LexiconTerm"]] = relationship(back_populates="category")


class LexiconTerm(Base):
    __tablename__ = "lexicon_terms"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lexicon_categories.id", ondelete="CASCADE"), nullable=False
    )
    term: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    abbreviation: Mapped[str | None] = mapped_column(String(64), nullable=True)
    definition: Mapped[str] = mapped_column(Text, nullable=False)
    model_scope: Mapped[str] = mapped_column(String(16), nullable=False, default="NEUTRAL")  # G|S|NEUTRAL
    canon_section_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_new_in_v34: Mapped[bool] = mapped_column(default=False, nullable=False)
    supersedes: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    category: Mapped[LexiconCategory] = relationship(back_populates="terms")
