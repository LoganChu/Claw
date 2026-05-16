"""Ingest node: pull today's events from the database into the graph state."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

from claw.database import get_db, get_events, get_recent_summaries
from claw.memory.store import retrieve_similar_sessions
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

    # Augment recent history with vector-similar past sessions for richer LLM context
    similar_query = f"Date: {session_id}. Git events: {len(git_events)}. Focus events: {len(focus_events)}."
    similar_sessions = await retrieve_similar_sessions(similar_query, n=3)
    # Merge similar sessions into history without duplicating entries already present
    existing_ids = {s.get("session_id") for s in history}
    for s in similar_sessions:
        if s.get("session_id") and s["session_id"] not in existing_ids:
            history.append(s)
            existing_ids.add(s["session_id"])

    logger.info(
        "[ingest] session=%s git=%d focus=%d calendar=%d goals=%d history=%d (incl. %d similar)",
        session_id,
        len(git_events),
        len(focus_events),
        len(calendar_events),
        len(goal_snapshots),
        len(history),
        len(similar_sessions),
    )

    return {
        "session_id": session_id,
        "git_events": git_events,
        "focus_events": focus_events,
        "calendar_events": calendar_events,
        "goal_snapshots": goal_snapshots,
        "historical_summaries": history,
    }
