"""CommunicationAgent — polls Slack for message volume to proxy communication load."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone, timedelta

import aiosqlite

from .base import BaseMonitorAgent

logger = logging.getLogger(__name__)


class CommunicationAgent(BaseMonitorAgent):
    """Counts Slack messages sent/received in the last poll window."""

    agent_name = "communication"

    def __init__(
        self,
        db: aiosqlite.Connection,
        poll_interval: int = 300,
    ) -> None:
        super().__init__(db, poll_interval)
        self._token = os.environ.get("SLACK_BOT_TOKEN", "")
        self._channels = [
            c.strip()
            for c in os.environ.get("SLACK_CHANNELS", "").split(",")
            if c.strip()
        ]
        self._client = None
        self._init_attempted = False
        self._last_poll_ts: float = (datetime.now(timezone.utc) - timedelta(seconds=poll_interval)).timestamp()

    def _build_client(self):
        if not self._token:
            logger.warning("SLACK_BOT_TOKEN not set; communication monitoring disabled")
            return None
        try:
            from slack_sdk.web.async_client import AsyncWebClient
            return AsyncWebClient(token=self._token)
        except ImportError:
            logger.warning("slack-sdk not installed; communication monitoring disabled")
            return None

    async def collect(self) -> list[tuple[str, dict]]:
        if not self._init_attempted:
            self._init_attempted = True
            self._client = self._build_client()

        if self._client is None:
            return []

        if not self._channels:
            logger.warning("[communication] SLACK_CHANNELS not set; skipping")
            return []

        now = datetime.now(timezone.utc)
        oldest = str(self._last_poll_ts)
        latest = str(now.timestamp())

        total_messages = 0
        active_channels = 0

        for channel in self._channels:
            try:
                resp = await self._client.conversations_history(
                    channel=channel,
                    oldest=oldest,
                    latest=latest,
                    limit=200,
                )
                msgs = resp.get("messages", [])
                if msgs:
                    total_messages += len(msgs)
                    active_channels += 1
            except Exception:
                logger.debug("[communication] failed to fetch channel %s", channel)

        self._last_poll_ts = now.timestamp()

        if total_messages == 0:
            return []

        payload = {
            "messages_total": total_messages,
            "active_channels": active_channels,
            "channels_monitored": len(self._channels),
            "window_seconds": int(now.timestamp() - float(oldest)),
            "timestamp": now.isoformat(),
        }
        logger.info("[communication] %d messages across %d channels", total_messages, active_channels)
        return [("communication_volume", payload)]
