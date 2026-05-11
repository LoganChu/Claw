"""PatternAnalyzer node: LLM-powered analysis of time patterns and productivity score."""
from __future__ import annotations

import json
import logging
import os

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from claw.pipeline.state import ProductivityState

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are an expert productivity analyst. Analyze a developer's work session data and:
1. Identify 2-4 specific patterns (e.g. "peak focus in late morning", "frequent context switches after meetings")
2. Compute a productivity score from 1-10 based on focus depth, output, and goal progress
3. Return ONLY valid JSON with keys: "patterns" (list of strings) and "score" (float 1-10)"""


async def pattern_analyzer(state: ProductivityState) -> dict:
    llm = ChatOpenAI(
        model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        temperature=0.1,
    )

    # Build concise context for the LLM (keep token count low)
    context = {
        "date": state.session_id,
        "focus_minutes": state.focus_minutes,
        "distracted_minutes": state.distracted_minutes,
        "meeting_minutes": state.meeting_minutes,
        "commit_count": state.commit_count,
        "goal_completion_pct": state.goal_completion_pct,
        "recent_commits": [
            {
                "hash": e["payload"].get("hash", ""),
                "message": e["payload"].get("message", "")[:80],
                "files": e["payload"].get("files_changed", 0),
            }
            for e in state.git_events[:5]
            if isinstance(e.get("payload"), dict)
        ],
        "historical_avg_focus": _historical_avg(state.historical_summaries, "focus_minutes"),
        "historical_avg_commits": _historical_avg(state.historical_summaries, "commit_count"),
    }

    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=f"Session data:\n{json.dumps(context, indent=2)}"),
    ]

    try:
        response = await llm.ainvoke(messages)
        raw = response.content.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        result = json.loads(raw)
        patterns = result.get("patterns", [])
        score = float(result.get("score", 5.0))
    except Exception:
        logger.exception("[pattern_analyzer] LLM call failed, using defaults")
        patterns = ["Unable to analyze patterns — insufficient data or LLM error"]
        score = 5.0

    logger.info("[pattern_analyzer] score=%.1f patterns=%d", score, len(patterns))
    return {"patterns": patterns, "predicted_score": score}


def _historical_avg(summaries: list[dict], field: str) -> float:
    values = [s[field] for s in summaries if s.get(field) is not None]
    return round(sum(values) / len(values), 1) if values else 0.0
