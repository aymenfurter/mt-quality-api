"""FastAPI dependencies for the GEMBA-Score API."""
from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status

from .config import Settings, get_settings
from .db import get_session
from .services.llm import LLMClientProtocol, get_llm_client
from .services.scoring import ScoringService


async def require_app_id(x_app_id: str | None = Header(default=None, alias="X-APP-ID")) -> str:
    """Ensure the mandatory X-APP-ID header is present and non-empty."""

    if not x_app_id or not x_app_id.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-APP-ID header",
        )
    return x_app_id.strip()


def provide_settings() -> Settings:
    return get_settings()


def provide_llm_client(settings: Settings = Depends(provide_settings)) -> LLMClientProtocol:
    return get_llm_client(settings)


def provide_scoring_service(
    settings: Settings = Depends(provide_settings),
    llm_client: LLMClientProtocol = Depends(provide_llm_client),
) -> ScoringService:
    return ScoringService(llm_client=llm_client, llm_model_name=settings.default_llm_model)


__all__ = [
    "provide_settings",
    "provide_llm_client",
    "provide_scoring_service",
    "require_app_id",
    "get_session",
]
