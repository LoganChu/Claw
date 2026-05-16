"""
A2A HTTP server — exposes the in-process A2A bus over HTTP/SSE so external
tools (nat CLI, dashboards, other processes) can subscribe to agent events.

Endpoints:
  GET  /events   — SSE stream of nat.atif.Step objects (JSON, one per line)
  POST /publish  — accept an event from an external agent and fan it to bus
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone

from aiohttp import web

from claw.a2a.bus import bus

logger = logging.getLogger(__name__)

_HOST = os.environ.get("A2A_HOST", "0.0.0.0")
_PORT = int(os.environ.get("A2A_PORT", "8765"))


async def _sse_handler(request: web.Request) -> web.StreamResponse:
    """SSE endpoint — streams every Step published to the bus as a JSON line."""
    response = web.StreamResponse()
    response.headers["Content-Type"] = "text/event-stream"
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    await response.prepare(request)

    queue = bus.subscribe()
    try:
        while True:
            step = await queue.get()
            payload = {
                "step_id": step.step_id,
                "timestamp": step.timestamp,
                "source": step.source,
                "message": step.message,
                "extra": step.extra or {},
                "observation": (
                    step.observation.results[0].content
                    if step.observation and step.observation.results
                    else None
                ),
            }
            line = f"data: {json.dumps(payload)}\n\n"
            await response.write(line.encode())
    except asyncio.CancelledError:
        pass
    except ConnectionResetError:
        logger.debug("[a2a/server] client disconnected from SSE stream")
    return response


async def _publish_handler(request: web.Request) -> web.Response:
    """Accept a JSON payload and publish it to the bus as a Step."""
    try:
        body = await request.json()
        agent_name = body.get("agent", "external")
        event_type = body.get("event_type", "unknown")
        payload = body.get("payload", {})
        await bus.publish(agent_name=agent_name, event_type=event_type, payload=payload)
        return web.json_response({"ok": True})
    except Exception as exc:
        logger.exception("[a2a/server] publish handler error")
        return web.json_response({"ok": False, "error": str(exc)}, status=400)


async def _health_handler(_request: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()})


def _build_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/events", _sse_handler)
    app.router.add_post("/publish", _publish_handler)
    app.router.add_get("/health", _health_handler)
    return app


async def run_server() -> None:
    """Start the A2A HTTP server as a long-running asyncio coroutine."""
    app = _build_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, _HOST, _PORT)
    await site.start()
    logger.info("[a2a/server] listening on http://%s:%d", _HOST, _PORT)
    try:
        await asyncio.Event().wait()  # run until cancelled
    finally:
        await runner.cleanup()
