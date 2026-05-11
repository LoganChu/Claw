"""FocusTrackerAgent — polls the active window title on Windows to detect focus state."""
from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime, timezone

import aiosqlite

from .base import BaseMonitorAgent

logger = logging.getLogger(__name__)

# Keywords that suggest a distraction vs deep work
_DISTRACTION_KEYWORDS = frozenset([
    "youtube", "twitter", "x.com", "reddit", "instagram", "facebook",
    "tiktok", "netflix", "twitch", "discord", "slack", "whatsapp",
    "telegram", "gmail", "outlook", "news", "espn",
])

_WORK_KEYWORDS = frozenset([
    "vscode", "code", "pycharm", "intellij", "vim", "nvim", "emacs",
    "terminal", "powershell", "cmd", "bash", "jupyter", "colab",
    "github", "gitlab", "jira", "linear", "figma", "notion",
    "claude", "chatgpt", "cursor", "copilot",
])


def _classify_window(title: str) -> str:
    lower = title.lower()
    if any(k in lower for k in _DISTRACTION_KEYWORDS):
        return "distracted"
    if any(k in lower for k in _WORK_KEYWORDS):
        return "focus"
    return "neutral"


async def _get_active_window_title() -> str | None:
    if sys.platform != "win32":
        return None
    try:
        import win32gui
        hwnd = await asyncio.to_thread(win32gui.GetForegroundWindow)
        return await asyncio.to_thread(win32gui.GetWindowText, hwnd) or None
    except Exception:
        return None


class FocusTrackerAgent(BaseMonitorAgent):
    """Samples the active window title and logs focus vs distraction state."""

    agent_name = "focus"

    def __init__(
        self,
        db: aiosqlite.Connection,
        poll_interval: int = 60,  # check every minute for finer granularity
    ) -> None:
        super().__init__(db, poll_interval)
        self._last_title: str | None = None
        self._last_state: str | None = None
        self._state_start: datetime = datetime.now(timezone.utc)

    async def collect(self) -> list[tuple[str, dict]]:
        title = await _get_active_window_title()
        if not title:
            return []

        state = _classify_window(title)
        events: list[tuple[str, dict]] = []

        if title != self._last_title:
            now = datetime.now(timezone.utc)
            duration_seconds = 0
            if self._last_state and self._last_title:
                duration_seconds = int((now - self._state_start).total_seconds())
                events.append((
                    "window_change",
                    {
                        "previous_title": self._last_title[:100],
                        "previous_state": self._last_state,
                        "duration_seconds": duration_seconds,
                        "new_title": title[:100],
                        "new_state": state,
                        "timestamp": now.isoformat(),
                    },
                ))

            self._last_title = title
            self._last_state = state
            self._state_start = now

        return events
