"""LangGraph state schema for the productivity analysis pipeline."""
from __future__ import annotations

from typing import Annotated, Any
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


class ProductivityState(BaseModel):
    # Input
    session_id: str = ""
    query: str = ""

    # Collected raw events (populated by Ingest node)
    git_events: list[dict[str, Any]] = Field(default_factory=list)
    focus_events: list[dict[str, Any]] = Field(default_factory=list)
    calendar_events: list[dict[str, Any]] = Field(default_factory=list)
    goal_snapshots: list[dict[str, Any]] = Field(default_factory=list)
    historical_summaries: list[dict[str, Any]] = Field(default_factory=list)

    # Computed metrics (populated by Classify node)
    focus_minutes: int = 0
    distracted_minutes: int = 0
    meeting_minutes: int = 0
    commit_count: int = 0
    classification_confidence: float = 0.0  # 0-1; low triggers a re-ingest cycle

    # Goal tracking (populated by GoalTracker node)
    goal_completion_pct: float = 0.0
    goal_details: list[dict[str, Any]] = Field(default_factory=list)

    # Analysis results (populated by PatternAnalyzer node)
    patterns: list[str] = Field(default_factory=list)
    predicted_score: float = 0.0

    # Final output (populated by InsightGenerator + ReportWriter)
    insights: list[str] = Field(default_factory=list)
    report_md: str = ""

    # Pipeline control
    retry_count: int = 0
    max_retries: int = 2
    messages: Annotated[list, add_messages] = Field(default_factory=list)
