"""Base class for all 24/7 monitor agents."""
from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone

import aiosqlite

from claw.a2a import bus
from claw.database import insert_event
from claw.safety import scrub_payload

logger = logging.getLogger(__name__)


class BaseMonitorAgent(ABC):
    """
    Runs in an async loop, polling for events and writing them to the event log.

    After each DB write the event is also published to the A2A bus as a
    nat.atif.Step, making it immediately available to any subscribed orchestrator.
    """

    agent_name: str  # must be set by subclasses

    def __init__(
        self,
        db: aiosqlite.Connection,
        poll_interval: int = 300,  # seconds
    ) -> None:
        self._db = db
        self._poll_interval = poll_interval
        self._running = False
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._loop(), name=self.agent_name)
        logger.info("[%s] started (poll every %ds)", self.agent_name, self._poll_interval)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("[%s] stopped", self.agent_name)

    async def _loop(self) -> None:
        while self._running:
            try:
                events = await self.collect()
                for event_type, payload in events:
                    safe_payload = scrub_payload(payload)

                    # Persist to SQLite event log
                    await insert_event(
                        self._db,
                        agent=self.agent_name,
                        event_type=event_type,
                        payload=safe_payload,
                    )
                    logger.debug("[%s] logged %s", self.agent_name, event_type)

                    # Publish to A2A bus as nat.atif.Step for real-time orchestration
                    await bus.publish(
                        agent_name=self.agent_name,
                        event_type=event_type,
                        payload=safe_payload,
                    )

            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("[%s] error during collection", self.agent_name)
            await asyncio.sleep(self._poll_interval)

    @abstractmethod
    async def collect(self) -> list[tuple[str, dict]]:
        """Return a list of (event_type, payload) pairs discovered this tick."""
        ...

    @property
    def session_id(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")
