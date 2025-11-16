"""SQLAlchemy models."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class TranslationScore(Base):
    __tablename__ = "TranslationScores"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    app_id: Mapped[str] = mapped_column(String(100), nullable=False)
    source_lang: Mapped[str] = mapped_column(String(50), nullable=False)
    target_lang: Mapped[str] = mapped_column(String(50), nullable=False)
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    target_text: Mapped[str] = mapped_column(Text, nullable=False)
    scoring_method: Mapped[str] = mapped_column(String(20), nullable=False)
    llm_model: Mapped[str] = mapped_column(String(50), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    adequacy_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    fluency_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_llm_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


__all__ = ["Base", "TranslationScore"]
