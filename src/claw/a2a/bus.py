"""
A2A event bus — asyncio pub/sub hub that fans ATIF Step events from monitor agents
to all subscribers (e.g., the analysis orchestrator).

Each event published by a monitor agent becomes a nat.atif.Step so the event stream
is native to the NeMo Agent Toolkit trajectory format.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

from nat.atif import Step
from nat.atif.observation import Observation
from nat.atif.observation_result import ObservationResult

logger = logging.getLogger(__name__)


class A2ABus:
    """Lightweight ATIF-native pub/sub bus for inter-agent event streaming."""

    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue[Step]] = []
        self._step_counter = 0

    def subscribe(self) -> asyncio.Queue[Step]:
        """Return a new queue that receives every published Step."""
        q: asyncio.Queue[Step] = asyncio.Queue()
        self._subscribers.append(q)
        return q

    async def publish(self, agent_name: str, event_type: str, payload: dict) -> None:
        """
        Publish one monitor-agent event as a nat.atif.Step to all subscribers.

        The payload is encoded in the Step's observation so the orchestrator can
        consume raw event data in the standard ATIF format.
        """
        self._step_counter += 1
        step = Step(
            step_id=self._step_counter,
            timestamp=datetime.now(timezone.utc).isoformat(),
            source="agent",
            message=f"[{agent_name}] {event_type}",
            extra={"agent": agent_name, "event_type": event_type},
            observation=Observation(
                results=[ObservationResult(content=json.dumps(payload, default=str))]
            ),
        )

        logger.debug("[A2A] %s → bus: %s (step %d)", agent_name, event_type, self._step_counter)

        for q in self._subscribers:
            await q.put(step)


# Module-level singleton shared across all agents in the same process.
bus: A2ABus = A2ABus()
