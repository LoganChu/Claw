"""
Claw live dashboard — Rich-based TUI that shows real-time agent events from the A2A bus.

Usage:
    from claw.dashboard import ClawApp
    app = ClawApp()
    asyncio.run(app.run())
"""
from __future__ import annotations

import asyncio
import json
import logging
from collections import deque
from datetime import datetime, timezone

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from claw.a2a import bus

logger = logging.getLogger(__name__)

_MAX_EVENTS = 20
_REFRESH_HZ = 4


class ClawApp:
    """Live dashboard subscribing to the A2A bus and displaying agent events."""

    def __init__(self) -> None:
        self._console = Console()
        self._events: deque[dict] = deque(maxlen=_MAX_EVENTS)
        self._focus_minutes: float = 0.0
        self._distracted_minutes: float = 0.0
        self._commit_count: int = 0
        self._latest_chart_path: str = ""
        self._stop = asyncio.Event()

    async def run(self) -> None:
        """Start the dashboard. Press Ctrl+C to quit."""
        queue = bus.subscribe()

        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=1),
        )
        layout["body"].split_row(
            Layout(name="events", ratio=3),
            Layout(name="metrics", ratio=1),
        )

        loop = asyncio.get_event_loop()
        loop.add_signal_handler(2, self._stop.set)  # SIGINT

        with Live(layout, console=self._console, refresh_per_second=_REFRESH_HZ, screen=True):
            consumer = asyncio.create_task(self._consume(queue))
            try:
                while not self._stop.is_set():
                    self._render(layout)
                    await asyncio.sleep(1 / _REFRESH_HZ)
            except asyncio.CancelledError:
                pass
            finally:
                consumer.cancel()
                try:
                    await consumer
                except asyncio.CancelledError:
                    pass

    async def _consume(self, queue: asyncio.Queue) -> None:
        while True:
            step = await queue.get()
            extra = step.extra or {}
            payload_str = ""
            if step.observation and step.observation.results:
                payload_str = step.observation.results[0].content[:120]
                try:
                    payload = json.loads(step.observation.results[0].content)
                    self._update_metrics(extra.get("agent", ""), payload)
                except (json.JSONDecodeError, TypeError):
                    pass

            self._events.append({
                "time": datetime.now(timezone.utc).strftime("%H:%M:%S"),
                "agent": extra.get("agent", "?"),
                "event": extra.get("event_type", "?"),
                "summary": payload_str,
            })

    def _update_metrics(self, agent: str, payload: dict) -> None:
        if agent == "focus":
            state = payload.get("state", "")
            duration = payload.get("duration_seconds", 60) / 60
            if state == "focus":
                self._focus_minutes += duration
            elif state == "distracted":
                self._distracted_minutes += duration
        elif agent == "git":
            self._commit_count += 1

    def _render(self, layout: Layout) -> None:
        layout["header"].update(
            Panel(
                Text("Claw — Live Productivity Dashboard", style="bold cyan", justify="center"),
                style="cyan",
            )
        )

        table = Table(expand=True, box=None, show_header=True, header_style="bold magenta")
        table.add_column("Time", style="dim", width=10)
        table.add_column("Agent", width=14)
        table.add_column("Event", width=22)
        table.add_column("Summary")
        for ev in reversed(self._events):
            agent_color = {
                "git": "green", "focus": "blue", "goal": "yellow",
                "calendar": "magenta", "communication": "cyan",
            }.get(ev["agent"], "white")
            table.add_row(
                ev["time"],
                Text(ev["agent"], style=agent_color),
                ev["event"],
                ev["summary"],
            )

        layout["events"].update(Panel(table, title="Agent Events", border_style="dim"))

        total = self._focus_minutes + self._distracted_minutes
        focus_pct = (self._focus_minutes / total * 100) if total else 0.0
        metrics_text = (
            f"[bold]Focus[/bold]      {self._focus_minutes:.0f}m ({focus_pct:.0f}%)\n"
            f"[bold]Distracted[/bold] {self._distracted_minutes:.0f}m\n"
            f"[bold]Commits[/bold]    {self._commit_count}\n"
        )
        layout["metrics"].update(Panel(metrics_text, title="Session", border_style="dim"))
        chart_note = f"  Chart: {self._latest_chart_path}" if self._latest_chart_path else ""
        layout["footer"].update(Text(f"Ctrl+C to quit{chart_note}", style="dim", justify="center"))
