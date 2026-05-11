"""Unit tests for the classify pipeline node."""
import pytest
from claw.pipeline.state import ProductivityState
from claw.pipeline.nodes.classify import classify, needs_more_data


def _make_focus_event(state: str, duration: int) -> dict:
    return {
        "agent": "focus",
        "event_type": "window_change",
        "payload": {"previous_state": state, "duration_seconds": duration, "new_state": "focus"},
    }


def test_classify_basic():
    state = ProductivityState(
        focus_events=[
            _make_focus_event("focus", 3600),       # 60 min focus
            _make_focus_event("distracted", 600),   # 10 min distracted
        ],
        git_events=[
            {"event_type": "commit", "agent": "git", "payload": {}},
            {"event_type": "commit", "agent": "git", "payload": {}},
        ],
    )
    result = classify(state)
    assert result["focus_minutes"] == 60
    assert result["distracted_minutes"] == 10
    assert result["commit_count"] == 2
    assert result["classification_confidence"] == 1.0  # 70min >> 30min threshold


def test_classify_low_confidence():
    state = ProductivityState(
        focus_events=[_make_focus_event("focus", 600)],  # only 10 min
    )
    result = classify(state)
    assert result["classification_confidence"] < 0.5


def test_needs_more_data_retry():
    state = ProductivityState(classification_confidence=0.3, retry_count=0)
    assert needs_more_data(state) == "retry"


def test_needs_more_data_continue_after_max_retries():
    state = ProductivityState(classification_confidence=0.3, retry_count=2)
    assert needs_more_data(state) == "continue"


def test_needs_more_data_continue_high_confidence():
    state = ProductivityState(classification_confidence=0.9, retry_count=0)
    assert needs_more_data(state) == "continue"
