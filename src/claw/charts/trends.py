"""Weekly trend chart generator — produces a PNG from the last 30 days of daily_summaries."""
from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


async def generate_trend_chart(session_id: str, days: int = 30) -> str | None:
    """
    Generate a 4-panel trend chart PNG for the given session.
    Returns the output file path, or None if matplotlib is unavailable or data is insufficient.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")  # non-interactive backend safe for server use
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        from datetime import datetime
    except ImportError:
        logger.warning("[charts] matplotlib not installed; skipping chart generation")
        return None

    from claw.database import get_db, get_recent_summaries

    db_path = os.environ.get("DB_PATH", "data/claw.db")
    db = await get_db(db_path)
    try:
        summaries = await get_recent_summaries(db, days=days)
    finally:
        await db.close()

    if len(summaries) < 2:
        logger.info("[charts] fewer than 2 summaries — skipping chart")
        return None

    # Sort oldest-first for plotting
    summaries.sort(key=lambda s: s.get("session_id", ""))

    dates = [datetime.strptime(s["session_id"], "%Y-%m-%d") for s in summaries]
    focus = [s.get("focus_minutes", 0) or 0 for s in summaries]
    distracted = [s.get("distracted_minutes", 0) or 0 for s in summaries]
    meetings = [s.get("meeting_minutes", 0) or 0 for s in summaries]
    commits = [s.get("commit_count", 0) or 0 for s in summaries]
    scores = [s.get("predicted_score", 0) or 0 for s in summaries]
    ratings = [s.get("self_rating") for s in summaries]

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    fig.suptitle(f"Productivity Trends — last {days} days (as of {session_id})", fontsize=13)

    date_fmt = mdates.DateFormatter("%m/%d")

    # Panel 1: Stacked time breakdown
    ax = axes[0, 0]
    ax.bar(dates, focus, label="Focus", color="#4CAF50", alpha=0.85)
    ax.bar(dates, distracted, bottom=focus, label="Distracted", color="#F44336", alpha=0.85)
    ax.bar(dates, meetings, bottom=[f + d for f, d in zip(focus, distracted)], label="Meetings", color="#2196F3", alpha=0.85)
    ax.set_title("Time Breakdown (min/day)")
    ax.xaxis.set_major_formatter(date_fmt)
    ax.legend(fontsize=8)
    ax.tick_params(axis="x", rotation=30)

    # Panel 2: Commits per day
    ax = axes[0, 1]
    ax.bar(dates, commits, color="#9C27B0", alpha=0.85)
    ax.set_title("Commits per Day")
    ax.xaxis.set_major_formatter(date_fmt)
    ax.tick_params(axis="x", rotation=30)

    # Panel 3: Productivity score vs self-rating
    ax = axes[1, 0]
    ax.plot(dates, scores, label="Predicted score", color="#FF9800", linewidth=2, marker="o", markersize=4)
    rated_dates = [d for d, r in zip(dates, ratings) if r is not None]
    rated_vals = [r * 2 for r in ratings if r is not None]  # scale 1-5 → 2-10
    if rated_dates:
        ax.plot(rated_dates, rated_vals, label="Self-rating (×2)", color="#03A9F4", linewidth=2, marker="s", markersize=4, linestyle="--")
    ax.set_title("Score vs Self-Rating")
    ax.set_ylim(0, 11)
    ax.xaxis.set_major_formatter(date_fmt)
    ax.legend(fontsize=8)
    ax.tick_params(axis="x", rotation=30)

    # Panel 4: Focus % trend
    ax = axes[1, 1]
    focus_pct = [
        (f / (f + d) * 100) if (f + d) > 0 else 0
        for f, d in zip(focus, distracted)
    ]
    ax.plot(dates, focus_pct, color="#4CAF50", linewidth=2, marker="o", markersize=4)
    ax.axhline(y=70, color="gray", linestyle="--", linewidth=1, alpha=0.6, label="70% target")
    ax.set_title("Focus Rate (%)")
    ax.set_ylim(0, 105)
    ax.xaxis.set_major_formatter(date_fmt)
    ax.legend(fontsize=8)
    ax.tick_params(axis="x", rotation=30)

    fig.tight_layout()

    output_dir = Path(os.environ.get("REPORT_OUTPUT_DIR", "reports")) / "charts"
    output_dir.mkdir(parents=True, exist_ok=True)
    chart_path = output_dir / f"{session_id}_trends.png"
    fig.savefig(chart_path, dpi=120, bbox_inches="tight")
    plt.close(fig)

    logger.info("[charts] saved trend chart → %s", chart_path)
    return str(chart_path)
