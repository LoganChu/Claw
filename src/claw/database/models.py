from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite


_SCHEMA = (Path(__file__).parent / "schema.sql").read_text()


async def get_db(path: str) -> aiosqlite.Connection:
    db = await aiosqlite.connect(path)
    db.row_factory = aiosqlite.Row
    await db.executescript(_SCHEMA)
    await db.commit()
    return db


async def insert_event(
    db: aiosqlite.Connection,
    *,
    agent: str,
    event_type: str,
    payload: dict[str, Any],
    session_id: str | None = None,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    sid = session_id or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    await db.execute(
        "INSERT INTO events (timestamp, agent, event_type, payload, session_id) VALUES (?, ?, ?, ?, ?)",
        (now, agent, event_type, json.dumps(payload), sid),
    )
    await db.commit()


async def get_events(
    db: aiosqlite.Connection,
    session_id: str,
    agent: str | None = None,
) -> list[dict[str, Any]]:
    if agent:
        cursor = await db.execute(
            "SELECT * FROM events WHERE session_id = ? AND agent = ? ORDER BY timestamp",
            (session_id, agent),
        )
    else:
        cursor = await db.execute(
            "SELECT * FROM events WHERE session_id = ? ORDER BY timestamp",
            (session_id,),
        )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def save_daily_summary(
    db: aiosqlite.Connection,
    session_id: str,
    *,
    focus_minutes: int,
    distracted_minutes: int,
    meeting_minutes: int,
    commit_count: int,
    goal_completion_pct: float,
    predicted_score: float,
    report_md: str,
    raw_insights: list[str],
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        """
        INSERT INTO daily_summaries
            (session_id, generated_at, focus_minutes, distracted_minutes, meeting_minutes,
             commit_count, goal_completion_pct, predicted_score, report_md, raw_insights)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(session_id) DO UPDATE SET
            generated_at = excluded.generated_at,
            focus_minutes = excluded.focus_minutes,
            distracted_minutes = excluded.distracted_minutes,
            meeting_minutes = excluded.meeting_minutes,
            commit_count = excluded.commit_count,
            goal_completion_pct = excluded.goal_completion_pct,
            predicted_score = excluded.predicted_score,
            report_md = excluded.report_md,
            raw_insights = excluded.raw_insights
        """,
        (
            session_id, now, focus_minutes, distracted_minutes, meeting_minutes,
            commit_count, goal_completion_pct, predicted_score, report_md,
            json.dumps(raw_insights),
        ),
    )
    await db.commit()


async def get_recent_summaries(
    db: aiosqlite.Connection, days: int = 14
) -> list[dict[str, Any]]:
    cursor = await db.execute(
        "SELECT * FROM daily_summaries ORDER BY session_id DESC LIMIT ?",
        (days,),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_active_goals(db: aiosqlite.Connection) -> list[dict[str, Any]]:
    cursor = await db.execute(
        "SELECT * FROM goals WHERE active = 1 ORDER BY id"
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]
