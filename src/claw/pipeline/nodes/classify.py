"""Classify node: compute time-block metrics from raw focus and calendar events."""
from __future__ import annotations

import logging

from claw.pipeline.state import ProductivityState

logger = logging.getLogger(__name__)

_MIN_DATA_MINUTES = 30  # minimum data for high-confidence classification


def classify(state: ProductivityState) -> dict:
    focus_seconds = 0
    distracted_seconds = 0

    for e in state.focus_events:
        payload = e.get("payload", {})
        if not isinstance(payload, dict):
            continue
        duration = payload.get("duration_seconds", 0)
        prev_state = payload.get("previous_state", "neutral")
        if prev_state == "focus":
            focus_seconds += duration
        elif prev_state == "distracted":
            distracted_seconds += duration

    # Calendar events contribute meeting minutes
    meeting_minutes = 0
    for e in state.calendar_events:
        payload = e.get("payload", {})
        if isinstance(payload, dict):
            meeting_minutes += payload.get("duration_minutes", 0)

    focus_minutes = focus_seconds // 60
    distracted_minutes = distracted_seconds // 60
    commit_count = sum(
        1 for e in state.git_events if e.get("event_type") == "commit"
    )

    total_classified = focus_minutes + distracted_minutes
    confidence = min(total_classified / _MIN_DATA_MINUTES, 1.0) if _MIN_DATA_MINUTES > 0 else 0.0

    logger.info(
        "[classify] focus=%dm distracted=%dm meetings=%dm commits=%d confidence=%.2f",
        focus_minutes, distracted_minutes, meeting_minutes, commit_count, confidence,
    )

    return {
        "focus_minutes": focus_minutes,
        "distracted_minutes": distracted_minutes,
        "meeting_minutes": meeting_minutes,
        "commit_count": commit_count,
        "classification_confidence": confidence,
    }


def needs_more_data(state: ProductivityState) -> str:
    """Routing function: cycle back to ingest if we don't have enough data yet."""
    if state.classification_confidence < 0.5 and state.retry_count < state.max_retries:
        logger.info("[classify] low confidence (%.2f), requesting re-ingest (retry %d)",
                    state.classification_confidence, state.retry_count + 1)
        return "retry"
    return "continue"
