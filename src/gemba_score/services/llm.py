"""Azure OpenAI client abstractions."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, TypedDict, TypeVar

import instructor
from openai import APIError, AsyncAzureOpenAI

from ..config import Settings, get_settings


class ChatMessage(TypedDict):
    role: str
    content: str


class LLMClientError(RuntimeError):
    """Raised when the LLM client cannot fulfill a request."""


class LLMClientProtocol(Protocol):
    async def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float = 0.0,
    ) -> str:
        """Execute a chat completion with the provided messages and return content."""

    async def parse(
        self,
        messages: Sequence[ChatMessage],
        response_model: type[T],
        *,
        temperature: float = 0.0,
    ) -> T:
        """Execute a completion and parse the structured response via Instructor."""


T = TypeVar("T")


@dataclass
class AzureOpenAIClient(LLMClientProtocol):
    """Thin wrapper over the official Azure OpenAI SDK."""

    settings: Settings

    def __post_init__(self) -> None:
        raw_client = AsyncAzureOpenAI(
            api_key=self.settings.azure_openai_api_key,
            api_version=self.settings.azure_openai_api_version,
            azure_endpoint=str(self.settings.azure_openai_endpoint),
        )
        self._client = instructor.patch(raw_client)
        self._deployment = self.settings.azure_openai_deployment

    async def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float = 0.0,
    ) -> str:
        try:
            response = await self._client.chat.completions.create(
                model=self._deployment,
                messages=list(messages),
                temperature=temperature,
            )
        except APIError as exc:  # pragma: no cover - depends on network issues
            raise LLMClientError(str(exc)) from exc

        choice = response.choices[0]
        content = choice.message.content or ""
        return content.strip()

    async def parse(
        self,
        messages: Sequence[ChatMessage],
        response_model: type[T],
        *,
        temperature: float = 0.0,
    ) -> T:
        try:
            return await self._client.chat.completions.parse(
                model=self._deployment,
                messages=list(messages),
                response_format=response_model,
                temperature=temperature,
            )
        except APIError as exc:  # pragma: no cover
            raise LLMClientError(str(exc)) from exc


_cached_client: AzureOpenAIClient | None = None


def get_llm_client(settings: Settings | None = None) -> AzureOpenAIClient:
    """Return a cached Azure OpenAI client instance."""

    global _cached_client
    settings = settings or get_settings()
    if _cached_client is None:
        _cached_client = AzureOpenAIClient(settings=settings)
    return _cached_client


__all__ = ["AzureOpenAIClient", "LLMClientProtocol", "LLMClientError", "get_llm_client"]
