from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator, Sequence
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
import pytest_asyncio

from gemba_score.config import get_settings
from gemba_score.db import reset_database
from gemba_score.dependencies import provide_llm_client
from gemba_score.main import create_app
from gemba_score.services.llm import ChatMessage, LLMClientProtocol

USE_REAL_AZURE = os.getenv("USE_REAL_AZURE_OPENAI") == "1"


class FakeLLMClient(LLMClientProtocol):
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def complete(self, messages: Sequence[ChatMessage], *, temperature: float = 0.0) -> str:  # noqa: ARG002
        last = messages[-1]["content"]
        self.calls.append(last)
        if "IMPORTANT: Output valid JSON only" in last:
            return (
                '{"score": 93.0, "adequacy": 4.5, "fluency": 4.0, '
                '"rationale": "Strong translation"}'
            )
        if "Annotated error spans" in last:
            return "Score (0-100): 87.0"
        if "Each error is classified as one of two categories" in last:
            return "no-error"
        if "Each error is classified as one of three categories" in last:
            return '{"score": -5, "analysis": "Major fluency issue"}'
        if "Score the following translation" in last:
            return "98.5"
        return "42"

    async def parse(
        self,
        messages: Sequence[ChatMessage],
        response_model,
        *,
        temperature: float = 0.0,  # noqa: ARG002
    ):
        if response_model.__name__ == "MQMEval":
            parsed = response_model(score=95.0, analysis="Stub MQM response")
        elif response_model.__name__ == "StructuredDAReturn":
            parsed = response_model(
                score=93.0,
                adequacy=4.5,
                fluency=4.0,
                rationale="Stub structured response",
            )
        else:
            raise AssertionError("Unexpected response model")

        message = SimpleNamespace(parsed=parsed)
        choice = SimpleNamespace(message=message)
        return SimpleNamespace(choices=[choice])


@pytest.fixture(autouse=True)
def _reset_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    get_settings.cache_clear()
    reset_database()
    if not USE_REAL_AZURE:
        db_file = tmp_path / "test.db"
        monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_file}")
    try:
        yield
    finally:
        get_settings.cache_clear()
        reset_database()


@pytest_asyncio.fixture()
async def client() -> AsyncIterator[tuple[httpx.AsyncClient, FakeLLMClient | None]]:
    app = create_app()
    fake_client: FakeLLMClient | None = None
    if not USE_REAL_AZURE:
        fake_client = FakeLLMClient()
        app.dependency_overrides[provide_llm_client] = lambda: fake_client
    await app.router.startup()
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as async_client:
            yield async_client, fake_client
    finally:
        await app.router.shutdown()
