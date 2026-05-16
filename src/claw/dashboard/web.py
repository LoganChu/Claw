"""
Claw web dashboard — Streamlit app for interactive productivity trend visualization.

Run with:
    streamlit run src/claw/dashboard/web.py
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path


def _get_summaries(days: int = 30) -> list[dict]:
    """Synchronous wrapper around the async DB call for Streamlit."""
    async def _fetch():
        from claw.database import get_db, get_recent_summaries
        db = await get_db(os.environ.get("DB_PATH", "data/claw.db"))
        try:
            return await get_recent_summaries(db, days=days)
        finally:
            await db.close()

    return asyncio.run(_fetch())


def main() -> None:
    try:
        import streamlit as st
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("Streamlit or matplotlib not installed. Run: pip install streamlit matplotlib")
        return

    st.set_page_config(page_title="Claw Dashboard", page_icon="🐾", layout="wide")
    st.title("Claw — Productivity Dashboard")

    days = st.sidebar.slider("Days to show", min_value=7, max_value=90, value=30)
    summaries = _get_summaries(days=days)

    if not summaries:
        st.warning("No session data found. Run `python main.py` first to collect data.")
        return

    summaries.sort(key=lambda s: s.get("session_id", ""))

    dates = [s["session_id"] for s in summaries]
    focus = [s.get("focus_minutes", 0) or 0 for s in summaries]
    distracted = [s.get("distracted_minutes", 0) or 0 for s in summaries]
    meetings = [s.get("meeting_minutes", 0) or 0 for s in summaries]
    commits = [s.get("commit_count", 0) or 0 for s in summaries]
    scores = [s.get("predicted_score", 0) or 0 for s in summaries]
    ratings = [s.get("self_rating") for s in summaries]

    # Summary KPIs
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Avg focus / day", f"{sum(focus) / len(focus):.0f} min")
    col2.metric("Avg commits / day", f"{sum(commits) / len(commits):.1f}")
    col3.metric("Avg score", f"{sum(scores) / len(scores):.1f} / 10")
    rated = [r for r in ratings if r is not None]
    col4.metric("Self-ratings collected", len(rated))

    # Charts
    fig, axes = plt.subplots(2, 2, figsize=(14, 8))
    fig.suptitle(f"Last {days} days", fontsize=13)

    axes[0, 0].bar(dates, focus, label="Focus", color="#4CAF50", alpha=0.85)
    axes[0, 0].bar(dates, distracted, bottom=focus, label="Distracted", color="#F44336", alpha=0.85)
    axes[0, 0].bar(dates, meetings, bottom=[f + d for f, d in zip(focus, distracted)], label="Meetings", color="#2196F3", alpha=0.85)
    axes[0, 0].set_title("Time Breakdown (min/day)")
    axes[0, 0].legend(fontsize=8)
    plt.setp(axes[0, 0].xaxis.get_majorticklabels(), rotation=45, ha="right")

    axes[0, 1].bar(dates, commits, color="#9C27B0", alpha=0.85)
    axes[0, 1].set_title("Commits per Day")
    plt.setp(axes[0, 1].xaxis.get_majorticklabels(), rotation=45, ha="right")

    axes[1, 0].plot(dates, scores, label="Predicted", color="#FF9800", marker="o", markersize=4)
    rated_dates = [d for d, r in zip(dates, ratings) if r is not None]
    rated_scaled = [r * 2 for r in ratings if r is not None]
    if rated_dates:
        axes[1, 0].plot(rated_dates, rated_scaled, label="Self-rated (×2)", color="#03A9F4", marker="s", markersize=4, linestyle="--")
    axes[1, 0].set_title("Score vs Self-Rating")
    axes[1, 0].set_ylim(0, 11)
    axes[1, 0].legend(fontsize=8)
    plt.setp(axes[1, 0].xaxis.get_majorticklabels(), rotation=45, ha="right")

    focus_pct = [(f / (f + d) * 100) if (f + d) > 0 else 0 for f, d in zip(focus, distracted)]
    axes[1, 1].plot(dates, focus_pct, color="#4CAF50", marker="o", markersize=4)
    axes[1, 1].axhline(y=70, color="gray", linestyle="--", alpha=0.6, label="70% target")
    axes[1, 1].set_title("Focus Rate (%)")
    axes[1, 1].set_ylim(0, 105)
    axes[1, 1].legend(fontsize=8)
    plt.setp(axes[1, 1].xaxis.get_majorticklabels(), rotation=45, ha="right")

    fig.tight_layout()
    st.pyplot(fig)
    plt.close(fig)

    # Latest report
    st.subheader("Latest Report")
    if summaries:
        latest = summaries[-1]
        report_path = Path(os.environ.get("REPORT_OUTPUT_DIR", "reports")) / f"{latest['session_id']}.md"
        if report_path.exists():
            st.markdown(report_path.read_text(encoding="utf-8"))
        else:
            st.info(f"No report file found for {latest['session_id']}.")


if __name__ == "__main__":
    main()
