"""Unit tests for the InsightGenerator pipeline node."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from claw.pipeline.state import ProductivityState
from claw.pipeline.nodes.insight_generator import insight_generator


def _make_state(**kwargs) -> ProductivityState:
    defaults = dict(
        session_id="2026-05-16",
        focus_minutes=90,
        distracted_minutes=45,
        commit_count=3,
        goal_completion_pct=50.0,
        predicted_score=6.5,
        patterns=["frequent context switches", "low morning productivity"],
        goal_details=[],
    )
    defaults.update(kwargs)
    return ProductivityState(**defaults)


@pytest.mark.asyncio
async def test_insight_generator_returns_list_of_strings():
    llm_response = MagicMock()
    llm_response.content = json.dumps(["Block distractions before 10am.", "Aim for 2+ commits per session."])

    with patch("claw.pipeline.nodes.insight_generator.ChatOpenAI") as MockLLM:
        instance = MockLLM.return_value
        instance.ainvoke = AsyncMock(return_value=llm_response)
        result = await insight_generator(_make_state())

    assert isinstance(result["insights"], list)
    assert len(result["insights"]) == 2
    assert "distractions" in result["insights"][0]


@pytest.mark.asyncio
async def test_insight_generator_strips_markdown_fence():
    llm_response = MagicMock()
    llm_response.content = "```json\n[\"insight one\", \"insight two\"]\n```"

    with patch("claw.pipeline.nodes.insight_generator.ChatOpenAI") as MockLLM:
        instance = MockLLM.return_value
        instance.ainvoke = AsyncMock(return_value=llm_response)
        result = await insight_generator(_make_state())

    assert result["insights"] == ["insight one", "insight two"]


@pytest.mark.asyncio
async def test_insight_generator_falls_back_on_llm_error():
    with patch("claw.pipeline.nodes.insight_generator.ChatOpenAI") as MockLLM:
        instance = MockLLM.return_value
        instance.ainvoke = AsyncMock(side_effect=RuntimeError("timeout"))
        result = await insight_generator(_make_state())

    assert len(result["insights"]) == 1


@pytest.mark.asyncio
async def test_insight_generator_wraps_non_list_response():
    llm_response = MagicMock()
    llm_response.content = json.dumps("single string insight")

    with patch("claw.pipeline.nodes.insight_generator.ChatOpenAI") as MockLLM:
        instance = MockLLM.return_value
        instance.ainvoke = AsyncMock(return_value=llm_response)
        result = await insight_generator(_make_state())

    assert isinstance(result["insights"], list)
    assert len(result["insights"]) == 1
