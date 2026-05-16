"""Integration tests for pipeline nodes (goal_tracker, report_writer, ingest)."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from claw.pipeline.state import ProductivityState
from claw.pipeline.nodes.goal_tracker import goal_tracker
from claw.pipeline.nodes.classify import classify


# ── goal_tracker ──────────────────────────────────────────────────────────────

def _goal_snapshot(goals: list[dict]) -> dict:
    return {
        "agent": "goal",
        "event_type": "goal_progress",
        "payload": {"goals": goals},
    }


def test_goal_tracker_no_snapshots():
    state = ProductivityState()
    result = goal_tracker(state)
    assert result["goal_completion_pct"] == 0.0
    assert result["goal_details"] == []


def test_goal_tracker_single_goal_complete():
    state = ProductivityState(
        goal_snapshots=[
            _goal_snapshot([{"title": "10 commits", "current": 10, "target": 10, "pct_complete": 100}])
        ]
    )
    result = goal_tracker(state)
    assert result["goal_completion_pct"] == 100.0
    assert len(result["goal_details"]) == 1


def test_goal_tracker_multiple_goals_averages():
    state = ProductivityState(
        goal_snapshots=[
            _goal_snapshot([
                {"title": "commits", "pct_complete": 80},
                {"title": "focus", "pct_complete": 60},
            ])
        ]
    )
    result = goal_tracker(state)
    assert result["goal_completion_pct"] == 70.0


def test_goal_tracker_uses_latest_snapshot():
    state = ProductivityState(
        goal_snapshots=[
            _goal_snapshot([{"title": "commits", "pct_complete": 10}]),
            _goal_snapshot([{"title": "commits", "pct_complete": 90}]),
        ]
    )
    result = goal_tracker(state)
    assert result["goal_completion_pct"] == 90.0


def test_goal_tracker_json_string_payload():
    payload_str = json.dumps({"goals": [{"title": "g", "pct_complete": 50}]})
    state = ProductivityState(
        goal_snapshots=[{"agent": "goal", "event_type": "goal_progress", "payload": payload_str}]
    )
    result = goal_tracker(state)
    assert result["goal_completion_pct"] == 50.0


def test_goal_tracker_empty_goals_list():
    state = ProductivityState(goal_snapshots=[_goal_snapshot([])])
    result = goal_tracker(state)
    assert result["goal_completion_pct"] == 0.0


# ── classify (calendar meeting_minutes) ───────────────────────────────────────

def test_classify_counts_meeting_minutes():
    state = ProductivityState(
        calendar_events=[
            {"agent": "calendar", "payload": {"duration_minutes": 30}},
            {"agent": "calendar", "payload": {"duration_minutes": 60}},
        ]
    )
    result = classify(state)
    assert result["meeting_minutes"] == 90


def test_classify_ignores_non_dict_payload():
    state = ProductivityState(
        focus_events=[{"agent": "focus", "payload": "broken"}],
    )
    result = classify(state)
    assert result["focus_minutes"] == 0
    assert result["distracted_minutes"] == 0


# ── ingest (mocked DB + mocked ChromaDB) ─────────────────────────────────────

@pytest.mark.asyncio
async def test_ingest_groups_events_by_agent():
    mock_events = [
        {"agent": "git", "event_type": "commit", "payload": "{}", "session_id": "2026-05-16"},
        {"agent": "focus", "event_type": "window_change", "payload": "{}", "session_id": "2026-05-16"},
        {"agent": "calendar", "event_type": "meeting_event", "payload": "{}", "session_id": "2026-05-16"},
        {"agent": "goal", "event_type": "goal_progress", "payload": "{}", "session_id": "2026-05-16"},
    ]

    with (
        patch("claw.pipeline.nodes.ingest.get_db", new_callable=AsyncMock) as mock_db_fn,
        patch("claw.pipeline.nodes.ingest.get_events", new_callable=AsyncMock, return_value=mock_events),
        patch("claw.pipeline.nodes.ingest.get_recent_summaries", new_callable=AsyncMock, return_value=[]),
        patch("claw.pipeline.nodes.ingest.retrieve_similar_sessions", new_callable=AsyncMock, return_value=[]),
    ):
        mock_conn = AsyncMock()
        mock_db_fn.return_value = mock_conn

        from claw.pipeline.nodes.ingest import ingest
        state = ProductivityState(session_id="2026-05-16")
        result = await ingest(state)

    assert len(result["git_events"]) == 1
    assert len(result["focus_events"]) == 1
    assert len(result["calendar_events"]) == 1
    assert len(result["goal_snapshots"]) == 1


@pytest.mark.asyncio
async def test_ingest_merges_similar_sessions_without_duplicates():
    db_history = [{"session_id": "2026-05-15", "focus_minutes": 120}]
    similar = [
        {"session_id": "2026-05-15", "focus_minutes": 120},  # duplicate — should be skipped
        {"session_id": "2026-05-10", "focus_minutes": 90},   # new — should be added
    ]

    with (
        patch("claw.pipeline.nodes.ingest.get_db", new_callable=AsyncMock) as mock_db_fn,
        patch("claw.pipeline.nodes.ingest.get_events", new_callable=AsyncMock, return_value=[]),
        patch("claw.pipeline.nodes.ingest.get_recent_summaries", new_callable=AsyncMock, return_value=db_history),
        patch("claw.pipeline.nodes.ingest.retrieve_similar_sessions", new_callable=AsyncMock, return_value=similar),
    ):
        mock_conn = AsyncMock()
        mock_db_fn.return_value = mock_conn

        from claw.pipeline.nodes.ingest import ingest
        state = ProductivityState(session_id="2026-05-16")
        result = await ingest(state)

    session_ids = [s["session_id"] for s in result["historical_summaries"]]
    assert session_ids.count("2026-05-15") == 1  # not duplicated
    assert "2026-05-10" in session_ids
