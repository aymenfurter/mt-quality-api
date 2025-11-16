from __future__ import annotations

import pytest
from sqlalchemy import func, select

from gemba_score.db import get_database
from gemba_score.models import TranslationScore
from gemba_score.schemas import ScoringMethod


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method",
    ["GEMBA-DA", "GEMBA-MQM", "GEMBA-ESA", "STRUCTURED-DA"],
)
async def test_score_endpoint_success(client, method):
    http_client, _ = client
    payload = {
        "source_lang": "English",
        "target_lang": "German",
        "source_text": "The quick brown fox jumps over the lazy dog.",
        "target_text": "Der schnelle braune Fuchs springt über den faulen Hund.",
        "method": method,
    }
    app_id = f"unit-test-client-{method.lower()}"
    database = get_database()
    async_session = database.sessionmaker()
    async with async_session() as session:
        before = (
            await session.execute(
                select(func.count()).where(TranslationScore.app_id == app_id)
            )
        ).scalar_one()
    response = await http_client.post(
        "/api/v1/score",
        json=payload,
        headers={"X-APP-ID": app_id},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["method_used"] == method
    assert body["request_id"]
    if method == "STRUCTURED-DA":
        assert body["adequacy"] is not None
        assert body["fluency"] is not None
        assert body["rationale"]
    else:
        assert body.get("adequacy") is None
        assert body.get("fluency") is None

    async with async_session() as session:
        after = (
            await session.execute(
                select(func.count()).where(TranslationScore.app_id == app_id)
            )
        ).scalar_one()
        assert after == before + 1
        stmt = (
            select(TranslationScore)
            .where(TranslationScore.app_id == app_id)
            .order_by(TranslationScore.created_at.desc())
        )
        record = (await session.execute(stmt)).scalars().first()
        assert record is not None
        assert record.scoring_method == method


@pytest.mark.asyncio
async def test_missing_app_id_header_returns_401(client):
    http_client, _ = client
    payload = {
        "source_lang": "English",
        "target_lang": "German",
        "source_text": "Hello",
        "target_text": "Hallo",
        "method": "GEMBA-DA",
    }
    response = await http_client.post("/api/v1/score", json=payload)
    assert response.status_code == 401
    assert "Missing X-APP-ID" in response.text


@pytest.mark.asyncio
async def test_list_scores_filters_by_threshold(client):
    http_client, _ = client
    database = get_database()
    async_session = database.sessionmaker()
    async with async_session() as session:
        high = TranslationScore(
            app_id="ui-test",
            source_lang="English",
            target_lang="German",
            source_text="hi",
            target_text="Hallo",
            scoring_method=ScoringMethod.GEMBA_DA.value,
            llm_model="fake",
            score=90.0,
        )
        low = TranslationScore(
            app_id="ui-test",
            source_lang="English",
            target_lang="German",
            source_text="bad",
            target_text="schlecht",
            scoring_method=ScoringMethod.GEMBA_DA.value,
            llm_model="fake",
            score=40.0,
        )
        session.add_all([high, low])
        await session.commit()

    resp = await http_client.get("/api/v1/scores", params={"threshold": 60})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert all(item["score"] <= 60 for item in data)


@pytest.mark.asyncio
async def test_dashboard_page_served(client):
    http_client, _ = client
    resp = await http_client.get("/")
    assert resp.status_code == 200
    assert "Analyst Console" in resp.text


@pytest.mark.asyncio
async def test_list_scores_filters_by_app_id(client):
    http_client, _ = client
    database = get_database()
    async_session = database.sessionmaker()
    async with async_session() as session:
        session.add_all(
            [
                TranslationScore(
                    app_id="widget-a",
                    source_lang="English",
                    target_lang="French",
                    source_text="Hello",
                    target_text="Bonjour",
                    scoring_method=ScoringMethod.GEMBA_DA.value,
                    llm_model="fake",
                    score=80,
                ),
                TranslationScore(
                    app_id="widget-b",
                    source_lang="English",
                    target_lang="French",
                    source_text="Hi",
                    target_text="Salut",
                    scoring_method=ScoringMethod.GEMBA_DA.value,
                    llm_model="fake",
                    score=70,
                ),
            ]
        )
        await session.commit()

    resp = await http_client.get("/api/v1/scores", params={"app_id": "widget-b"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["app_id"] == "widget-b"
