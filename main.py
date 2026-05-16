"""
Claw — 24/7 autonomous productivity tracking agent.

Usage:
    python main.py                  # start all agents + scheduled analysis
    python main.py --report         # run analysis now and print report
    python main.py --report --date 2026-05-09  # report for a specific date

Environment:
    Copy .env.example to .env and fill in your values.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown

load_dotenv()

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("claw")
console = Console()


async def run_analysis(session_id: str = "") -> str:
    """Run the LangGraph analysis pipeline and return the markdown report."""
    from claw.pipeline import compiled_graph, ProductivityState

    sid = session_id or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    state = ProductivityState(session_id=sid, query=f"Analyze productivity for {sid}")

    logger.info("Running analysis pipeline for session %s", sid)
    result = await compiled_graph.ainvoke(state)

    # compiled_graph returns a dict with all state fields
    if isinstance(result, dict):
        return result.get("report_md", "No report generated.")
    return result.report_md if hasattr(result, "report_md") else "No report generated."


async def _a2a_consumer() -> None:
    """Log all A2A bus events to the console in real time."""
    from claw.a2a import bus

    queue = bus.subscribe()
    while True:
        step = await queue.get()
        extra = step.extra or {}
        logger.debug(
            "[A2A] %s/%s — %s",
            extra.get("agent", "?"),
            extra.get("event_type", "?"),
            step.message,
        )


async def run_agents() -> None:
    """Start all monitor agents, the A2A server, the A2A consumer, and the periodic analysis scheduler."""
    from claw.database import get_db
    from claw.agents import (
        GitMonitorAgent,
        FocusTrackerAgent,
        GoalCheckAgent,
        CalendarAgent,
        CommunicationAgent,
    )
    from claw.a2a import run_server

    db_path = os.environ.get("DB_PATH", "data/claw.db")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    db = await get_db(db_path)
    poll_interval = int(os.environ.get("POLL_INTERVAL_SECONDS", 300))
    analysis_interval = int(os.environ.get("ANALYSIS_INTERVAL_MINUTES", 60)) * 60
    eod_hour = int(os.environ.get("EOD_REPORT_HOUR", 18))

    agents = [
        GitMonitorAgent(db, poll_interval=poll_interval),
        FocusTrackerAgent(db, poll_interval=60),
        GoalCheckAgent(db, poll_interval=1800),
    ]

    # Optional agents — activated when their credentials are present
    if os.environ.get("GOOGLE_CALENDAR_ID") or (Path("credentials.json").exists()):
        agents.append(CalendarAgent(db, poll_interval=poll_interval))
        logger.info("CalendarAgent enabled")

    if os.environ.get("SLACK_BOT_TOKEN"):
        agents.append(CommunicationAgent(db, poll_interval=poll_interval))
        logger.info("CommunicationAgent enabled")

    for agent in agents:
        agent.start()

    # A2A HTTP server — exposes SSE stream + publish endpoint for external consumers
    a2a_server_task = asyncio.create_task(run_server(), name="a2a_server")

    # A2A bus consumer — closes the pub/sub loop by logging all published events
    consumer_task = asyncio.create_task(_a2a_consumer(), name="a2a_consumer")

    console.print("[bold green]Claw is running[/bold green] — press Ctrl+C to stop")
    console.print(f"  Monitor agents: {', '.join(a.agent_name for a in agents)}")
    console.print(f"  Analysis every {analysis_interval // 60}min, EOD report at {eod_hour:02d}:00")

    stop_event = asyncio.Event()

    def _handle_signal(*_):
        stop_event.set()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    last_analysis = 0.0
    while not stop_event.is_set():
        now = asyncio.get_event_loop().time()

        # Periodic analysis
        if now - last_analysis >= analysis_interval:
            try:
                report = await run_analysis()
                console.print(Markdown(report[:500] + "…"))
            except Exception:
                logger.exception("Scheduled analysis failed")
            last_analysis = now

        await asyncio.sleep(10)

    # Graceful shutdown
    for task in (a2a_server_task, consumer_task):
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    logger.info("Shutting down monitor agents…")
    for agent in agents:
        await agent.stop()
    await db.close()
    console.print("[yellow]Claw stopped.[/yellow]")


def main() -> None:
    parser = argparse.ArgumentParser(description="Claw productivity agent")
    parser.add_argument("--report", action="store_true", help="Run analysis and print report, then exit")
    parser.add_argument("--date", default="", help="Session date for --report (YYYY-MM-DD)")
    parser.add_argument("--dashboard", action="store_true", help="Launch the live Rich dashboard")
    parser.add_argument("--optimize", action="store_true", help="Run NeMo prompt optimizer over recent rated sessions")
    args = parser.parse_args()

    if args.optimize:
        from claw.optimizer import run_prompt_optimizer
        import json as _json
        result = asyncio.run(run_prompt_optimizer())
        console.print(_json.dumps(result, indent=2))
    elif args.report:
        report = asyncio.run(run_analysis(args.date))
        console.print(Markdown(report))
    elif args.dashboard:
        from claw.dashboard import ClawApp
        asyncio.run(ClawApp().run())
    else:
        asyncio.run(run_agents())


if __name__ == "__main__":
    main()
