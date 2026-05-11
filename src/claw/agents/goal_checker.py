"""GoalCheckAgent — periodically evaluates goal progress against the event log."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import aiosqlite

from claw.database import get_events, get_active_goals
from .base import BaseMonitorAgent

logger = logging.getLogger(__name__)


class GoalCheckAgent(BaseMonitorAgent):
    """Reads active goals and current event counts, logs progress snapshots."""

    agent_name = "goal"

    def __init__(
        self,
        db: aiosqlite.Connection,
        poll_interval: int = 1800,  # check every 30 min
    ) -> None:
        super().__init__(db, poll_interval)

    async def collect(self) -> list[tuple[str, dict]]:
        session_id = self.session_id
        goals = await get_active_goals(self._db)
        if not goals:
            return []

        events = await get_events(self._db, session_id)
        commit_count = sum(1 for e in events if e["agent"] == "git" and e["event_type"] == "commit")
        focus_seconds = sum(
            e.get("payload", {}).get("duration_seconds", 0)
            for e in events
            if e["agent"] == "focus" and e.get("payload", {}).get("previous_state") == "focus"
            if isinstance(e.get("payload"), dict)
        )

        import json
        goal_snapshots = []
        for goal in goals:
            metric = goal["metric"]
            target = goal["target"]
            if metric == "commit_count":
                value = commit_count
            elif metric == "focus_minutes":
                value = focus_seconds / 60.0
            else:
                continue

            pct = min(value / target * 100, 100) if target > 0 else 0
            goal_snapshots.append({
                "goal_id": goal["id"],
                "title": goal["title"],
                "metric": metric,
                "target": target,
                "current": value,
                "pct_complete": round(pct, 1),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        if goal_snapshots:
            return [("goal_progress_snapshot", {"goals": goal_snapshots, "session_id": session_id})]
        return []
