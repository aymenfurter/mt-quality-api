"""Scoring service orchestrating Azure OpenAI prompts."""
from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from pydantic import BaseModel

from ..prompts import (
    gemba_da_prompt,
    gemba_esa_error_prompt,
    gemba_esa_scoring_prompt,
    gemba_mqm_few_shot_user,
    gemba_mqm_final_user,
    gemba_mqm_system_prompt,
    structured_da_system_message,
    structured_da_user_message,
)
from ..schemas import ScoreRequest, ScoringMethod
from .llm import ChatMessage, LLMClientProtocol


class ScoringServiceError(RuntimeError):
    """Raised when scoring fails (e.g., no numeric score could be parsed)."""


@dataclass(slots=True)
class ScoreComputation:
    method: ScoringMethod
    score: float
    llm_model: str
    raw_response: str
    adequacy: float | None = None
    fluency: float | None = None
    rationale: str | None = None


class ScoringService:
    """Generates GEMBA scores using a backing LLM client."""

    def __init__(self, llm_client: LLMClientProtocol, llm_model_name: str) -> None:
        self._llm = llm_client
        self._llm_model_name = llm_model_name

    async def score(self, payload: ScoreRequest) -> ScoreComputation:
        method = payload.method
        if method == ScoringMethod.GEMBA_DA:
            return await self._score_gemba_da(payload)
        if method == ScoringMethod.GEMBA_MQM:
            return await self._score_gemba_mqm(payload)
        if method == ScoringMethod.GEMBA_ESA:
            return await self._score_gemba_esa(payload)
        if method == ScoringMethod.STRUCTURED_DA:
            return await self._score_structured_da(payload)
        raise ScoringServiceError(f"Unsupported scoring method: {method}")

    async def _score_gemba_da(self, payload: ScoreRequest) -> ScoreComputation:
        messages: Sequence[ChatMessage] = [
            {"role": "user", "content": gemba_da_prompt(payload)}
        ]
        response = await self._llm.complete(messages)
        score = _extract_last_number(response)
        return ScoreComputation(
            method=payload.method,
            score=score,
            llm_model=self._llm_model_name,
            raw_response=response,
        )

    async def _score_gemba_mqm(self, payload: ScoreRequest) -> ScoreComputation:
        few_shot_assistant = (
            '{"score": 100, "analysis": "No errors detected; translation is perfect."}'
        )
        messages: Sequence[ChatMessage] = [
            {"role": "system", "content": gemba_mqm_system_prompt()},
            {"role": "user", "content": gemba_mqm_few_shot_user()},
            {"role": "assistant", "content": few_shot_assistant},
            {"role": "user", "content": gemba_mqm_final_user(payload)},
        ]
        raw = await self._llm.parse(messages, response_model=MQMEval)
        parsed = _expect_parsed(raw)
        score_value = float(parsed.score)
        return ScoreComputation(
            method=payload.method,
            score=score_value,
            llm_model=self._llm_model_name,
            raw_response=parsed.model_dump_json(),
            rationale=parsed.analysis,
        )

    async def _score_gemba_esa(self, payload: ScoreRequest) -> ScoreComputation:
        error_messages: Sequence[ChatMessage] = [
            {"role": "user", "content": gemba_esa_error_prompt(payload)}
        ]
        error_analysis = await self._llm.complete(error_messages)

        score_messages: Sequence[ChatMessage] = [
            {
                "role": "user",
                "content": gemba_esa_scoring_prompt(payload, error_analysis),
            }
        ]
        score_response = await self._llm.complete(score_messages)
        score = _extract_last_number(score_response)
        combined_raw = f"Errors:\n{error_analysis}\n---\nScore:\n{score_response}"
        return ScoreComputation(
            method=payload.method,
            score=score,
            llm_model=self._llm_model_name,
            raw_response=combined_raw,
        )

    async def _score_structured_da(self, payload: ScoreRequest) -> ScoreComputation:
        messages: Sequence[ChatMessage] = [
            {"role": "system", "content": structured_da_system_message()},
            {"role": "user", "content": structured_da_user_message(payload)},
        ]
        raw = await self._llm.parse(messages, response_model=StructuredDAReturn)
        parsed = _expect_parsed(raw)
        return ScoreComputation(
            method=payload.method,
            score=float(parsed.score),
            llm_model=self._llm_model_name,
            raw_response=parsed.model_dump_json(),
            adequacy=parsed.adequacy,
            fluency=parsed.fluency,
            rationale=parsed.rationale,
        )


def _extract_last_number(text: str) -> float:
    matches = re.findall(r"-?\d+(?:\.\d+)?", text)
    if not matches:
        raise ScoringServiceError("Could not parse numeric score from LLM response")
    return float(matches[-1])


class MQMEval(BaseModel):
    score: float
    analysis: str


class StructuredDAReturn(BaseModel):
    score: float
    adequacy: float
    fluency: float
    rationale: str


def _expect_parsed(response) -> BaseModel:
    message = response.choices[0].message  # type: ignore[index]
    parsed = getattr(message, "parsed", None)
    if parsed is None:
        raise ScoringServiceError("LLM response missing structured payload")
    return parsed


__all__ = ["ScoringService", "ScoringServiceError", "ScoreComputation"]
