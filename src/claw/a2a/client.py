"""
A2A HTTP client — publish events to the A2A server from any process.
Falls back to the in-process bus when the server is not reachable (useful in tests).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os

import httpx

logger = logging.getLogger(__name__)

_A2A_BASE = "http://{host}:{port}".format(
    host=os.environ.get("A2A_HOST", "localhost"),
    port=os.environ.get("A2A_PORT", "8765"),
)


async def publish_event(agent_name: str, event_type: str, payload: dict) -> None:
    """
    Publish an event to the A2A server.
    Falls back to the in-process bus if the server is unreachable.
    """
    url = f"{_A2A_BASE}/publish"
    body = {"agent": agent_name, "event_type": event_type, "payload": payload}
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.post(url, json=body)
            resp.raise_for_status()
    except Exception:
        logger.debug("[a2a/client] server unreachable, falling back to in-process bus")
        from claw.a2a.bus import bus
        await bus.publish(agent_name=agent_name, event_type=event_type, payload=payload)


async def stream_events(on_event):
    """
    Subscribe to the A2A server SSE stream.
    Calls `on_event(step_dict)` for each received Step.
    Falls back to subscribing to the in-process bus if server is unreachable.
    """
    url = f"{_A2A_BASE}/events"
    try:
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("GET", url) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            step_dict = json.loads(line[6:])
                            await on_event(step_dict)
                        except json.JSONDecodeError:
                            pass
    except Exception:
        logger.debug("[a2a/client] SSE stream failed, falling back to in-process bus")
        from claw.a2a.bus import bus
        queue = bus.subscribe()
        while True:
            step = await queue.get()
            await on_event({
                "step_id": step.step_id,
                "message": step.message,
                "extra": step.extra or {},
            })
