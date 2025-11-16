"""Centralized prompt builders for GEMBA scoring methods."""
from __future__ import annotations

from textwrap import dedent

from .schemas import ScoreRequest


def gemba_da_prompt(payload: ScoreRequest) -> str:
    template = dedent(
        """
        Score the following translation from {source_lang} to {target_lang} on a continuous
        scale from 0 to 100, where a score of zero means "no meaning preserved" and score of one
        hundred means "perfect meaning and grammar".

        {source_lang} source: "{source_text}"
        {target_lang} translation: "{target_text}"
        Score:
        """
    ).strip()
    return template.format(
        source_lang=payload.source_lang,
        target_lang=payload.target_lang,
        source_text=payload.source_text,
        target_text=payload.target_text,
    )


def gemba_mqm_system_prompt() -> str:
    return dedent(
        """
        You are an expert MQM evaluator. Identify translation errors and output a holistic quality
        score on a 0-100 scale (0 = unusable, 100 = perfect). Return ONLY JSON: {"score": number,
        "analysis": string describing notable errors}.
        """
    ).strip()


def gemba_mqm_few_shot_user() -> str:
    return dedent(
        """
        English source:
        ```Hello world.```
        German translation:
        ```Hallo Welt.```

        Based on the source segment and machine translation surrounded with triple backticks,
        identify error types in the translation and classify them.
        """
    ).strip()


def gemba_mqm_final_user(payload: ScoreRequest) -> str:
    template = dedent(
        """
        {source_lang} source:
        ```{source_text}```
        {target_lang} translation:
        ```{target_text}```

        Based on the source segment and machine translation surrounded with triple backticks,
        identify error types in the translation and classify them. The categories of errors are:
        accuracy (addition, mistranslation, omission, untranslated text), fluency (character
        encoding, grammar, inconsistency, punctuation, register, spelling), style (awkward),
        terminology (inappropriate for context, inconsistent use), non-translation, other, or
        no-error. Each error is classified as one of three categories: critical, major, and minor.
        Critical errors inhibit comprehension of the text. Major errors disrupt the flow, but what
        the text is trying to say is still understandable. Minor errors are technically errors, but
        do not disrupt the flow or hinder comprehension.
        """
    ).strip()
    return template.format(
        source_lang=payload.source_lang,
        target_lang=payload.target_lang,
        source_text=payload.source_text,
        target_text=payload.target_text,
    )


def gemba_esa_error_prompt(payload: ScoreRequest) -> str:
    template = dedent(
        """
        {source_lang} source:
        ```{source_text}```
        {target_lang} translation:
        ```{target_text}```

        Based on the source segment and machine translation surrounded with triple backticks,
        identify error types in the translation and classify them. The categories of errors are:
        accuracy (addition, mistranslation, omission, untranslated text), fluency (character
        encoding, grammar, inconsistency, punctuation, register, spelling), style (awkward),
        terminology (inappropriate for context, inconsistent use), non-translation, other, or
        no-error. Each error is classified as one of two categories: major or minor. Major errors
        disrupt the flow and make the understandability of text difficult or impossible. Minor
        errors are errors that do not disrupt the flow significantly and what the text is trying to
        say is still understandable.
        """
    ).strip()
    return template.format(
        source_lang=payload.source_lang,
        target_lang=payload.target_lang,
        source_text=payload.source_text,
        target_text=payload.target_text,
    )


def gemba_esa_scoring_prompt(payload: ScoreRequest, errors: str) -> str:
    template = dedent(
        """
        Given the translation from {source_lang} to {target_lang} and the annotated error spans,
        assign a score on a continuous scale from 0 to 100. The scale has following reference
        points:
        0="No meaning preserved", 33="Some meaning preserved", 66="Most meaning preserved and few
        grammar mistakes", up to 100="Perfect meaning and grammar".

        Score the following translation from {source_lang} source:
        ```{source_text}```
        {target_lang} translation:
        ```{target_text}```
        Annotated error spans:
        ```{errors}```
        Score (0-100):
        """
    ).strip()
    return template.format(
        source_lang=payload.source_lang,
        target_lang=payload.target_lang,
        source_text=payload.source_text,
        target_text=payload.target_text,
        errors=errors,
    )


def structured_da_system_message() -> str:
    return (
        "You are an expert bilingual evaluator of machine translation quality. Be strict but fair."
    )


def structured_da_user_message(payload: ScoreRequest) -> str:
    template = dedent(
        """
        Evaluate the quality of the following machine translation from {source_lang} to
        {target_lang}.
        Return ONLY a JSON object with these fields:
        score: holistic quality 0-100 (float)
        adequacy: semantic accuracy and completeness 0-5 (float, where 5 = perfect meaning
        preservation)
        fluency: grammatical correctness and naturalness 0-5 (float, where 5 = perfect native
        fluency)
        rationale: brief explanation of the score (1-2 sentences)

        {source_lang} source: {source_text}
        {target_lang} hypothesis: {target_text}

        IMPORTANT: Output valid JSON only, no markdown fences or extra text.
        """
    ).strip()
    return template.format(
        source_lang=payload.source_lang,
        target_lang=payload.target_lang,
        source_text=payload.source_text,
        target_text=payload.target_text,
    )


__all__ = [
    "gemba_da_prompt",
    "gemba_mqm_system_prompt",
    "gemba_mqm_few_shot_user",
    "gemba_mqm_final_user",
    "gemba_esa_error_prompt",
    "gemba_esa_scoring_prompt",
    "structured_da_system_message",
    "structured_da_user_message",
]
