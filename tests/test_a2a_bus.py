"""Unit tests for the A2A event bus."""
from __future__ import annotations

import asyncio
import json

import pytest

from claw.a2a.bus import A2ABus


@pytest.mark.asyncio
async def test_subscribe_returns_queue():
    bus = A2ABus()
    q = bus.subscribe()
    assert isinstance(q, asyncio.Queue)


@pytest.mark.asyncio
async def test_publish_delivers_to_subscriber():
    bus = A2ABus()
    q = bus.subscribe()

    await bus.publish(agent_name="git", event_type="commit", payload={"hash": "abc123"})

    step = q.get_nowait()
    assert step.message == "[git] commit"
    assert step.extra["agent"] == "git"
    assert step.extra["event_type"] == "commit"


@pytest.mark.asyncio
async def test_publish_fans_out_to_multiple_subscribers():
    bus = A2ABus()
    q1 = bus.subscribe()
    q2 = bus.subscribe()

    await bus.publish(agent_name="focus", event_type="window_change", payload={"state": "focus"})

    assert not q1.empty()
    assert not q2.empty()


@pytest.mark.asyncio
async def test_step_contains_payload_in_observation():
    bus = A2ABus()
    q = bus.subscribe()
    payload = {"messages_total": 12, "active_channels": 2}

    await bus.publish(agent_name="communication", event_type="communication_volume", payload=payload)

    step = q.get_nowait()
    assert step.observation is not None
    content = step.observation.results[0].content
    decoded = json.loads(content)
    assert decoded["messages_total"] == 12


@pytest.mark.asyncio
async def test_step_ids_increment():
    bus = A2ABus()
    q = bus.subscribe()

    await bus.publish("git", "commit", {"hash": "aaa"})
    await bus.publish("git", "commit", {"hash": "bbb"})

    step1 = q.get_nowait()
    step2 = q.get_nowait()
    assert step2.step_id == step1.step_id + 1


@pytest.mark.asyncio
async def test_no_subscribers_publish_does_not_raise():
    bus = A2ABus()
    await bus.publish("goal", "goal_progress_snapshot", {"goals": []})
