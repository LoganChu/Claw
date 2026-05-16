"""Unit tests for the PatternAnalyzer pipeline node."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from claw.pipeline.state import ProductivityState
from claw.pipeline.nodes.pattern_analyzer import pattern_analyzer, _historical_avg


def _make_state(**kwargs) -> ProductivityState:
    defaults = dict(
        session_id="2026-05-16",
        focus_minutes=120,
        distracted_minutes=30,
        meeting_minutes=60,
        commit_count=5,
        goal_completion_pct=75.0,
        git_events=[],
        historical_summaries=[],
    )
    defaults.update(kwargs)
    return ProductivityState(**defaults)


@pytest.mark.asyncio
async def test_pattern_analyzer_returns_patterns_and_score():
    llm_response = MagicMock()
    llm_response.content = json.dumps({"patterns": ["peak focus in morning"], "score": 7.5})

    with patch("claw.pipeline.nodes.pattern_analyzer.ChatOpenAI") as MockLLM:
        instance = MockLLM.return_value
        instance.ainvoke = AsyncMock(return_value=llm_response)
        result = await pattern_analyzer(_make_state())

    assert len(result["patterns"]) == 1
    assert result["patterns"][0] == "peak focus in morning"
    assert result["predicted_score"] == 7.5


@pytest.mark.asyncio
async def test_pattern_analyzer_strips_markdown_fence():
    llm_response = MagicMock()
    llm_response.content = "```json\n{\"patterns\": [\"deep work blocks\"], \"score\": 8.0}\n```"

    with patch("claw.pipeline.nodes.pattern_analyzer.ChatOpenAI") as MockLLM:
        instance = MockLLM.return_value
        instance.ainvoke = AsyncMock(return_value=llm_response)
        result = await pattern_analyzer(_make_state())

    assert result["patterns"] == ["deep work blocks"]
    assert result["predicted_score"] == 8.0


@pytest.mark.asyncio
async def test_pattern_analyzer_falls_back_on_llm_error():
    with patch("claw.pipeline.nodes.pattern_analyzer.ChatOpenAI") as MockLLM:
        instance = MockLLM.return_value
        instance.ainvoke = AsyncMock(side_effect=RuntimeError("LLM unavailable"))
        result = await pattern_analyzer(_make_state())

    assert result["predicted_score"] == 5.0
    assert len(result["patterns"]) == 1


@pytest.mark.asyncio
async def test_pattern_analyzer_falls_back_on_bad_json():
    llm_response = MagicMock()
    llm_response.content = "not valid json at all"

    with patch("claw.pipeline.nodes.pattern_analyzer.ChatOpenAI") as MockLLM:
        instance = MockLLM.return_value
        instance.ainvoke = AsyncMock(return_value=llm_response)
        result = await pattern_analyzer(_make_state())

    assert result["predicted_score"] == 5.0


def test_historical_avg_computes_correctly():
    summaries = [
        {"focus_minutes": 100},
        {"focus_minutes": 200},
        {"focus_minutes": 150},
    ]
    avg = _historical_avg(summaries, "focus_minutes")
    assert avg == 150.0


def test_historical_avg_empty_returns_zero():
    assert _historical_avg([], "focus_minutes") == 0.0


def test_historical_avg_ignores_missing_field():
    summaries = [{"commit_count": 3}, {"other_field": 10}]
    avg = _historical_avg(summaries, "commit_count")
    assert avg == 3.0
