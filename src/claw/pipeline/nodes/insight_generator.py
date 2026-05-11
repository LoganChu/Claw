"""InsightGenerator node: produce 3-5 actionable insights from patterns and metrics."""
from __future__ import annotations

import json
import logging
import os

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from claw.pipeline.state import ProductivityState

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a productivity coach for software engineers.
Given a developer's work session analysis, generate 3-5 specific, actionable insights.
Each insight should reference concrete data from the session.
Return ONLY a JSON array of strings, e.g. ["Insight 1.", "Insight 2.", ...]"""


async def insight_generator(state: ProductivityState) -> dict:
    llm = ChatOpenAI(
        model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        temperature=0.4,
    )

    context = {
        "date": state.session_id,
        "productivity_score": state.predicted_score,
        "focus_minutes": state.focus_minutes,
        "distracted_minutes": state.distracted_minutes,
        "commit_count": state.commit_count,
        "goal_completion_pct": state.goal_completion_pct,
        "patterns": state.patterns,
        "goals": state.goal_details,
    }

    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=f"Session analysis:\n{json.dumps(context, indent=2)}"),
    ]

    try:
        response = await llm.ainvoke(messages)
        raw = response.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        insights: list[str] = json.loads(raw)
        if not isinstance(insights, list):
            insights = [str(insights)]
    except Exception:
        logger.exception("[insight_generator] LLM call failed")
        insights = ["Run the analysis again when more session data is available."]

    logger.info("[insight_generator] generated %d insights", len(insights))
    return {"insights": insights}
