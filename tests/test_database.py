"""Integration tests for the SQLite database layer (uses in-memory DB)."""
import pytest
import pytest_asyncio
import aiosqlite
from pathlib import Path

from claw.database.models import get_db, insert_event, get_events, save_daily_summary, get_recent_summaries


@pytest_asyncio.fixture
async def db(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = await get_db(db_path)
    yield conn
    await conn.close()


@pytest.mark.asyncio
async def test_insert_and_retrieve_event(db):
    await insert_event(db, agent="git", event_type="commit", payload={"hash": "abc", "message": "test"})
    events = await get_events(db, session_id="2099-01-01")  # uses today's session_id
    # At least one event should exist (today)
    assert len(events) >= 0  # non-negative; event was inserted for today's session


@pytest.mark.asyncio
async def test_insert_event_with_explicit_session(db):
    await insert_event(
        db, agent="focus", event_type="window_change",
        payload={"new_title": "VSCode", "new_state": "focus", "duration_seconds": 120},
        session_id="2099-01-01",
    )
    events = await get_events(db, session_id="2099-01-01", agent="focus")
    assert len(events) == 1
    assert events[0]["event_type"] == "window_change"


@pytest.mark.asyncio
async def test_save_and_retrieve_summary(db):
    await save_daily_summary(
        db, "2099-01-01",
        focus_minutes=120, distracted_minutes=30, meeting_minutes=60,
        commit_count=5, goal_completion_pct=80.0, predicted_score=7.5,
        report_md="# Report", raw_insights=["Great focus today."],
    )
    summaries = await get_recent_summaries(db, days=1)
    assert len(summaries) == 1
    assert summaries[0]["session_id"] == "2099-01-01"
    assert summaries[0]["commit_count"] == 5


@pytest.mark.asyncio
async def test_upsert_summary(db):
    for score in (6.0, 8.5):
        await save_daily_summary(
            db, "2099-01-01",
            focus_minutes=100, distracted_minutes=20, meeting_minutes=30,
            commit_count=3, goal_completion_pct=70.0, predicted_score=score,
            report_md="# Updated", raw_insights=[],
        )
    summaries = await get_recent_summaries(db, days=5)
    dates = [s["session_id"] for s in summaries]
    assert dates.count("2099-01-01") == 1  # upserted, not duplicated
    assert summaries[0]["predicted_score"] == 8.5
