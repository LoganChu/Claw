"""Unit tests for the ReportWriter pipeline node."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from claw.pipeline.state import ProductivityState
from claw.pipeline.nodes.report_writer import report_writer, _render_score_bar


def _make_state(**kwargs) -> ProductivityState:
    defaults = dict(
        session_id="2026-05-16",
        focus_minutes=120,
        distracted_minutes=30,
        meeting_minutes=45,
        commit_count=4,
        goal_completion_pct=80.0,
        predicted_score=7.5,
        patterns=["peak focus in morning"],
        insights=["Block distractions before 10am."],
        goal_details=[{"title": "Write tests", "current": 8, "target": 10, "pct_complete": 80}],
        git_events=[
            {"payload": {"hash": "abc1234", "message": "feat: add tests"}},
        ],
    )
    defaults.update(kwargs)
    return ProductivityState(**defaults)


def test_render_score_bar_full():
    bar = _render_score_bar(10.0, width=10)
    assert bar == "█" * 10


def test_render_score_bar_empty():
    bar = _render_score_bar(0.0, width=10)
    assert bar == "░" * 10


def test_render_score_bar_half():
    bar = _render_score_bar(5.0, width=10)
    assert "█" in bar and "░" in bar
    assert len(bar) == 10


@pytest.mark.asyncio
async def test_report_writer_returns_markdown(tmp_path):
    with (
        patch("claw.pipeline.nodes.report_writer.get_db", new_callable=AsyncMock) as mock_db,
        patch("claw.pipeline.nodes.report_writer.save_daily_summary", new_callable=AsyncMock),
        patch("claw.pipeline.nodes.report_writer.upsert_summary", new_callable=AsyncMock),
        patch.dict("os.environ", {"REPORT_OUTPUT_DIR": str(tmp_path)}),
    ):
        mock_db.return_value.__aenter__ = AsyncMock(return_value=mock_db.return_value)
        mock_db.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_db.return_value.close = AsyncMock()

        result = await report_writer(_make_state())

    md = result["report_md"]
    assert "# Productivity Report — 2026-05-16" in md
    assert "7.5 / 10" in md
    assert "120 min" in md  # focus_minutes
    assert "4" in md        # commit_count
    assert "Block distractions before 10am." in md
    assert "Write tests" in md


@pytest.mark.asyncio
async def test_report_writer_writes_file(tmp_path):
    with (
        patch("claw.pipeline.nodes.report_writer.get_db", new_callable=AsyncMock) as mock_db,
        patch("claw.pipeline.nodes.report_writer.save_daily_summary", new_callable=AsyncMock),
        patch("claw.pipeline.nodes.report_writer.upsert_summary", new_callable=AsyncMock),
        patch.dict("os.environ", {"REPORT_OUTPUT_DIR": str(tmp_path)}),
    ):
        mock_db.return_value.close = AsyncMock()
        await report_writer(_make_state())

    report_file = tmp_path / "2026-05-16.md"
    assert report_file.exists()
    assert "Productivity Report" in report_file.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_report_writer_no_goals_shows_placeholder(tmp_path):
    state = _make_state(goal_details=[], goal_completion_pct=0.0)
    with (
        patch("claw.pipeline.nodes.report_writer.get_db", new_callable=AsyncMock) as mock_db,
        patch("claw.pipeline.nodes.report_writer.save_daily_summary", new_callable=AsyncMock),
        patch("claw.pipeline.nodes.report_writer.upsert_summary", new_callable=AsyncMock),
        patch.dict("os.environ", {"REPORT_OUTPUT_DIR": str(tmp_path)}),
    ):
        mock_db.return_value.close = AsyncMock()
        result = await report_writer(state)

    assert "No active goals" in result["report_md"]


@pytest.mark.asyncio
async def test_report_writer_no_insights_shows_placeholder(tmp_path):
    state = _make_state(insights=[])
    with (
        patch("claw.pipeline.nodes.report_writer.get_db", new_callable=AsyncMock) as mock_db,
        patch("claw.pipeline.nodes.report_writer.save_daily_summary", new_callable=AsyncMock),
        patch("claw.pipeline.nodes.report_writer.upsert_summary", new_callable=AsyncMock),
        patch.dict("os.environ", {"REPORT_OUTPUT_DIR": str(tmp_path)}),
    ):
        mock_db.return_value.close = AsyncMock()
        result = await report_writer(state)

    assert "Insufficient data" in result["report_md"]
