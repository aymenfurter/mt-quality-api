"""Pydantic schemas for API I/O."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field, constr


class ScoringMethod(str, Enum):
    GEMBA_DA = "GEMBA-DA"
    GEMBA_MQM = "GEMBA-MQM"
    GEMBA_ESA = "GEMBA-ESA"
    STRUCTURED_DA = "STRUCTURED-DA"


class ScoreRequest(BaseModel):
    source_lang: constr(strip_whitespace=True, min_length=1) = Field(
        description="Full source language name"
    )
    target_lang: constr(strip_whitespace=True, min_length=1)
    source_text: constr(strip_whitespace=True, min_length=1)
    target_text: constr(strip_whitespace=True, min_length=1)
    method: ScoringMethod


class ScoreResponse(BaseModel):
    score: float
    method_used: ScoringMethod
    request_id: UUID
    adequacy: float | None = None
    fluency: float | None = None
    rationale: str | None = None


class ErrorResponse(BaseModel):
    error: str
    details: str | None = None


class TranslationScoreRecord(BaseModel):
    id: UUID
    app_id: str
    source_lang: str
    target_lang: str
    scoring_method: ScoringMethod
    llm_model: str
    score: float
    adequacy_score: float | None = None
    fluency_score: float | None = None
    rationale: str | None = None
    created_at: datetime
    target_text: str
