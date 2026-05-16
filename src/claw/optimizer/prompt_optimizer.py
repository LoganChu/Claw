"""
NeMo prompt optimizer — tunes the PatternAnalyzer and InsightGenerator system prompts
using past sessions where the user provided a self-rating.

Uses NAT's PromptOptimizer when available, with a simple gradient-free fallback.
Persists the best prompts to data/optimized_prompts.json.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_PROMPTS_PATH = Path(os.environ.get("DB_PATH", "data/claw.db")).parent / "optimized_prompts.json"

_DEFAULT_PROMPTS = {
    "pattern_analyzer": (
        "You are an expert productivity analyst. Analyze a developer's work session data and:\n"
        "1. Identify 2-4 specific patterns (e.g. \"peak focus in late morning\", \"frequent context switches after meetings\")\n"
        "2. Compute a productivity score from 1-10 based on focus depth, output, and goal progress\n"
        "3. Return ONLY valid JSON with keys: \"patterns\" (list of strings) and \"score\" (float 1-10)"
    ),
    "insight_generator": (
        "You are a productivity coach for software engineers.\n"
        "Given a developer's work session analysis, generate 3-5 specific, actionable insights.\n"
        "Each insight should reference concrete data from the session.\n"
        "Return ONLY a JSON array of strings, e.g. [\"Insight 1.\", \"Insight 2.\", ...]"
    ),
}


def load_optimized_prompts() -> dict[str, str]:
    """Load persisted optimized prompts, falling back to defaults if not found."""
    if _PROMPTS_PATH.exists():
        try:
            saved = json.loads(_PROMPTS_PATH.read_text(encoding="utf-8"))
            return {**_DEFAULT_PROMPTS, **saved}
        except Exception:
            logger.warning("[optimizer] failed to load optimized prompts, using defaults")
    return dict(_DEFAULT_PROMPTS)


async def run_prompt_optimizer(days: int = 30) -> dict:
    """
    Tune PatternAnalyzer and InsightGenerator prompts using rated sessions.
    Requires at least 5 rated sessions. Uses NAT's PromptOptimizer when available.
    Returns a summary of what was optimized.
    """
    from claw.database import get_db, get_recent_summaries

    db_path = os.environ.get("DB_PATH", "data/claw.db")
    db = await get_db(db_path)
    try:
        summaries = await get_recent_summaries(db, days=days)
    finally:
        await db.close()

    rated = [s for s in summaries if s.get("self_rating") is not None and s.get("focus_minutes") is not None]

    if len(rated) < 5:
        return {
            "status": "skipped",
            "reason": f"Need at least 5 rated sessions, have {len(rated)}",
        }

    # Build training pairs: (session_metrics_json, expected_score_1_to_10)
    training_pairs = [
        {
            "input": json.dumps({
                "focus_minutes": s.get("focus_minutes", 0),
                "distracted_minutes": s.get("distracted_minutes", 0),
                "commit_count": s.get("commit_count", 0),
                "goal_completion_pct": s.get("goal_completion_pct", 0),
            }),
            "expected_score": s["self_rating"] * 2,  # normalise 1-5 → 2-10
        }
        for s in rated
    ]

    optimized: dict[str, str] = {}

    # Attempt NAT PromptOptimizer
    try:
        from nat.optimizer import PromptOptimizer

        current_prompts = load_optimized_prompts()
        model = os.environ.get("ANALYSIS_MODEL", os.environ.get("OPENAI_MODEL", "gpt-4o-mini"))

        for node_name in ("pattern_analyzer", "insight_generator"):
            optimizer = PromptOptimizer(
                model=model,
                base_prompt=current_prompts[node_name],
                metric="correlation",
            )
            best = optimizer.fit(training_pairs)
            optimized[node_name] = best
            logger.info("[optimizer] %s → new prompt (len=%d)", node_name, len(best))

    except ImportError:
        logger.info("[optimizer] nat.optimizer not available — using heuristic fallback")
        optimized = _heuristic_tune(training_pairs)

    # Persist
    _PROMPTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _PROMPTS_PATH.write_text(json.dumps(optimized, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("[optimizer] saved optimized prompts → %s", _PROMPTS_PATH)

    return {
        "status": "ok",
        "rated_sessions": len(rated),
        "nodes_optimized": list(optimized.keys()),
        "prompts_path": str(_PROMPTS_PATH),
    }


def _heuristic_tune(training_pairs: list[dict]) -> dict[str, str]:
    """
    Fallback when NAT's optimizer is unavailable.
    Adds a few-shot example derived from the highest- and lowest-rated sessions
    to the default prompts, which typically improves calibration.
    """
    pairs_sorted = sorted(training_pairs, key=lambda p: p["expected_score"])
    low = pairs_sorted[0]
    high = pairs_sorted[-1]

    example_block = (
        f"\n\nExamples from past sessions:\n"
        f"- Low productivity ({low['expected_score']:.0f}/10): {low['input']}\n"
        f"- High productivity ({high['expected_score']:.0f}/10): {high['input']}"
    )

    return {
        "pattern_analyzer": _DEFAULT_PROMPTS["pattern_analyzer"] + example_block,
        "insight_generator": _DEFAULT_PROMPTS["insight_generator"],
    }
