"""Ingest node: pull today's events from the database into the graph state."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

from claw.database import get_db, get_events, get_recent_summaries
from claw.pipeline.state import ProductivityState

logger = logging.getLogger(__name__)


async def ingest(state: ProductivityState) -> dict:
    session_id = state.session_id or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    db_path = os.environ.get("DB_PATH", "data/claw.db")

    db = await get_db(db_path)
    try:
        all_events = await get_events(db, session_id)
        history = await get_recent_summaries(db, days=14)
    finally:
        await db.close()

    git_events = [e for e in all_events if e["agent"] == "git"]
    focus_events = [e for e in all_events if e["agent"] == "focus"]
    calendar_events = [e for e in all_events if e["agent"] == "calendar"]
    goal_snapshots = [e for e in all_events if e["agent"] == "goal"]

    # Deserialise JSON payloads
    for event_list in (git_events, focus_events, calendar_events, goal_snapshots):
        for e in event_list:
            if isinstance(e.get("payload"), str):
                try:
                    e["payload"] = json.loads(e["payload"])
                except json.JSONDecodeError:
                    pass

    logger.info(
        "[ingest] session=%s git=%d focus=%d calendar=%d goals=%d history=%d",
        session_id,
        len(git_events),
        len(focus_events),
        len(calendar_events),
        len(goal_snapshots),
        len(history),
    )

    return {
        "session_id": session_id,
        "git_events": git_events,
        "focus_events": focus_events,
        "calendar_events": calendar_events,
        "goal_snapshots": goal_snapshots,
        "historical_summaries": history,
    }
