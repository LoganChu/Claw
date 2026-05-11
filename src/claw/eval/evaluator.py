"""
Evaluation system: collect user self-ratings and compare against
the pipeline's predicted productivity score. Uses NeMo Agent Toolkit's
evaluation hooks when available, otherwise falls back to simple tracking.
"""
from __future__ import annotations

import json
import logging
import os

import aiosqlite

from claw.database import get_db, get_recent_summaries

logger = logging.getLogger(__name__)


async def record_self_rating(session_id: str, rating: int) -> None:
    """Record user's 1-5 self-rating for a completed session."""
    assert 1 <= rating <= 5, "Rating must be 1-5"
    db_path = os.environ.get("DB_PATH", "data/claw.db")
    db = await get_db(db_path)
    try:
        await db.execute(
            "UPDATE daily_summaries SET self_rating = ? WHERE session_id = ?",
            (rating, session_id),
        )
        await db.commit()
        logger.info("[eval] recorded self_rating=%d for %s", rating, session_id)
    finally:
        await db.close()


async def compute_accuracy_report(days: int = 30) -> dict:
    """
    Compare predicted_score (pipeline output) against self_rating (user input).
    Returns correlation stats and the sessions used.
    """
    db_path = os.environ.get("DB_PATH", "data/claw.db")
    db = await get_db(db_path)
    try:
        summaries = await get_recent_summaries(db, days=days)
    finally:
        await db.close()

    rated = [
        s for s in summaries
        if s.get("predicted_score") is not None and s.get("self_rating") is not None
    ]

    if len(rated) < 2:
        return {"error": "Need at least 2 rated sessions", "rated_sessions": len(rated)}

    # Normalise predicted score (1-10) → 1-5 scale for comparison
    pairs = [(s["predicted_score"] / 2, s["self_rating"]) for s in rated]
    pred_vals = [p[0] for p in pairs]
    true_vals = [p[1] for p in pairs]

    n = len(pairs)
    mean_pred = sum(pred_vals) / n
    mean_true = sum(true_vals) / n

    cov = sum((p - mean_pred) * (t - mean_true) for p, t in pairs) / n
    std_pred = (sum((p - mean_pred) ** 2 for p in pred_vals) / n) ** 0.5
    std_true = (sum((t - mean_true) ** 2 for t in true_vals) / n) ** 0.5

    correlation = (cov / (std_pred * std_true)) if std_pred > 0 and std_true > 0 else 0.0
    mae = sum(abs(p - t) for p, t in pairs) / n

    report = {
        "rated_sessions": n,
        "correlation": round(correlation, 3),
        "mean_absolute_error": round(mae, 2),
        "mean_predicted": round(mean_pred, 2),
        "mean_self_rated": round(mean_true, 2),
        "sessions": [
            {
                "date": s["session_id"],
                "predicted": round(s["predicted_score"] / 2, 1),
                "self_rated": s["self_rating"],
                "delta": round(abs(s["predicted_score"] / 2 - s["self_rating"]), 1),
            }
            for s in rated
        ],
    }
    logger.info("[eval] correlation=%.3f mae=%.2f over %d sessions", correlation, mae, n)
    return report
