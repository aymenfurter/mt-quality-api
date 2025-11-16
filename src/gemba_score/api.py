"""FastAPI router exposing the scoring endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .dependencies import (
    get_session,
    provide_scoring_service,
    require_app_id,
)
from .models import TranslationScore
from .schemas import (
    ErrorResponse,
    ScoreRequest,
    ScoreResponse,
    ScoringMethod,
    TranslationScoreRecord,
)
from .services.scoring import ScoringService, ScoringServiceError

router = APIRouter(tags=["Scoring"])


@router.post(
    "/score",
    response_model=ScoreResponse,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def score_translation(
    payload: ScoreRequest,
    app_id: str = Depends(require_app_id),
    scoring_service: ScoringService = Depends(provide_scoring_service),
    session: AsyncSession = Depends(get_session),
) -> ScoreResponse:
    """Score a translation using the requested GEMBA method and persist the outcome."""

    try:
        result = await scoring_service.score(payload)
    except ScoringServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    record = TranslationScore(
        app_id=app_id,
        source_lang=payload.source_lang,
        target_lang=payload.target_lang,
        source_text=payload.source_text,
        target_text=payload.target_text,
        scoring_method=payload.method.value,
        llm_model=result.llm_model,
        score=result.score,
        adequacy_score=result.adequacy,
        fluency_score=result.fluency,
        rationale=result.rationale,
        raw_llm_response=result.raw_response,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)

    return ScoreResponse(
        score=result.score,
        method_used=payload.method,
        request_id=record.id,
        adequacy=result.adequacy,
        fluency=result.fluency,
        rationale=result.rationale,
    )


@router.get(
    "/scores",
    response_model=list[TranslationScoreRecord],
    responses={401: {"model": ErrorResponse}},
)
async def list_scores(
    limit: int = Query(default=25, ge=1, le=200),
    threshold: float | None = Query(default=None, ge=0, le=100),
    app_id: str | None = Query(default=None, min_length=1),
    session: AsyncSession = Depends(get_session),
) -> list[TranslationScoreRecord]:
    """Return recent translation scores, optionally filtered by threshold/app-id."""

    stmt = select(TranslationScore).order_by(TranslationScore.created_at.desc()).limit(limit)
    if threshold is not None:
        stmt = stmt.where(TranslationScore.score <= threshold)
    if app_id:
        stmt = stmt.where(TranslationScore.app_id == app_id)

    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [
        TranslationScoreRecord(
            id=row.id,
            app_id=row.app_id,
            source_lang=row.source_lang,
            target_lang=row.target_lang,
            scoring_method=ScoringMethod(row.scoring_method),
            llm_model=row.llm_model,
            score=row.score,
            adequacy_score=row.adequacy_score,
            fluency_score=row.fluency_score,
            rationale=row.rationale,
            created_at=row.created_at,
            target_text=row.target_text,
        )
        for row in rows
    ]


__all__ = ["router"]
