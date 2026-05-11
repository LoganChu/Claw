"""GoalTracker node: compute goal completion from the latest goal progress snapshot."""
from __future__ import annotations

import json
import logging

from claw.pipeline.state import ProductivityState

logger = logging.getLogger(__name__)


def goal_tracker(state: ProductivityState) -> dict:
    if not state.goal_snapshots:
        return {"goal_completion_pct": 0.0, "goal_details": []}

    # Take the latest snapshot
    latest_snapshot_event = state.goal_snapshots[-1]
    payload = latest_snapshot_event.get("payload", {})
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return {"goal_completion_pct": 0.0, "goal_details": []}

    goals = payload.get("goals", [])
    if not goals:
        return {"goal_completion_pct": 0.0, "goal_details": goals}

    avg_pct = sum(g.get("pct_complete", 0) for g in goals) / len(goals)

    logger.info("[goal_tracker] %d goals, avg completion=%.1f%%", len(goals), avg_pct)
    return {"goal_completion_pct": round(avg_pct, 1), "goal_details": goals}
