"""Unit tests for monitor agents."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from claw.agents.git_monitor import GitMonitorAgent
from claw.agents.focus_tracker import FocusTrackerAgent, _classify_window
from claw.agents.communication_agent import CommunicationAgent


# ── GitMonitorAgent ───────────────────────────────────────────────────────────

def test_git_agent_name():
    db = AsyncMock()
    agent = GitMonitorAgent(db)
    assert agent.agent_name == "git"


@pytest.mark.asyncio
async def test_git_agent_returns_empty_on_bad_repo(tmp_path):
    db = AsyncMock()
    with patch.dict("os.environ", {"GIT_REPO_PATH": str(tmp_path)}):
        agent = GitMonitorAgent(db, poll_interval=300)
    result = await agent.collect()
    assert result == []


@pytest.mark.asyncio
async def test_git_agent_extracts_commit(tmp_path):
    db = AsyncMock()
    agent = GitMonitorAgent(db, repo_path=tmp_path, poll_interval=300)

    mock_commit = MagicMock()
    mock_commit.hexsha = "abc1234def56"
    mock_commit.message = "feat: add feature\n"
    mock_commit.author.name = "Logan"
    mock_commit.committed_date = 1747440000
    mock_commit.stats.files = {"a.py": {}, "b.py": {}, "c.py": {}}
    mock_commit.stats.total = {"insertions": 20, "deletions": 5}

    mock_repo = MagicMock()
    mock_repo.iter_commits.return_value = [mock_commit]
    mock_repo.active_branch.name = "main"

    with patch("git.Repo", return_value=mock_repo):
        result = await agent.collect()

    assert len(result) == 1
    event_type, payload = result[0]
    assert event_type == "commit"
    assert payload["hash"] == "abc1234def56"
    assert payload["message"] == "feat: add feature"
    assert payload["files_changed"] == 3
    assert payload["insertions"] == 20


@pytest.mark.asyncio
async def test_git_agent_deduplicates_seen_commits(tmp_path):
    db = AsyncMock()
    agent = GitMonitorAgent(db, repo_path=tmp_path, poll_interval=300)

    mock_commit = MagicMock()
    mock_commit.hexsha = "abc1234def56"
    mock_commit.message = "fix: bug\n"
    mock_commit.author.name = "Logan"
    mock_commit.committed_date = 1747440000
    mock_commit.stats.files = {"a.py": {}}
    mock_commit.stats.total = {"insertions": 5, "deletions": 2}

    mock_repo = MagicMock()
    mock_repo.iter_commits.return_value = [mock_commit]
    mock_repo.active_branch.name = "main"

    with patch("git.Repo", return_value=mock_repo):
        first = await agent.collect()
        second = await agent.collect()

    assert len(first) == 1
    assert len(second) == 0


# ── FocusTrackerAgent — _classify_window (pure function) ─────────────────────

def test_classify_window_distraction():
    assert _classify_window("YouTube - Google Chrome") == "distracted"


def test_classify_window_focus():
    assert _classify_window("main.py - Visual Studio Code") == "focus"


def test_classify_window_neutral():
    assert _classify_window("Windows File Explorer") == "neutral"


def test_focus_agent_name():
    db = AsyncMock()
    agent = FocusTrackerAgent(db)
    assert agent.agent_name == "focus"


@pytest.mark.asyncio
async def test_focus_agent_emits_on_title_change():
    db = AsyncMock()
    agent = FocusTrackerAgent(db)

    with patch("claw.agents.focus_tracker._get_active_window_title", new_callable=AsyncMock) as mock_title:
        mock_title.return_value = "YouTube - Google Chrome"
        await agent.collect()  # first call: sets state, no event emitted yet

        mock_title.return_value = "main.py - Visual Studio Code"
        result = await agent.collect()  # title changed — should emit window_change

    assert len(result) == 1
    event_type, payload = result[0]
    assert event_type == "window_change"
    assert payload["previous_state"] == "distracted"
    assert payload["new_state"] == "focus"


@pytest.mark.asyncio
async def test_focus_agent_no_event_on_same_title():
    db = AsyncMock()
    agent = FocusTrackerAgent(db)

    with patch("claw.agents.focus_tracker._get_active_window_title", new_callable=AsyncMock) as mock_title:
        mock_title.return_value = "main.py - Visual Studio Code"
        await agent.collect()  # first call
        result = await agent.collect()  # same title — no event

    assert result == []


@pytest.mark.asyncio
async def test_focus_agent_no_event_when_no_window():
    db = AsyncMock()
    agent = FocusTrackerAgent(db)

    with patch("claw.agents.focus_tracker._get_active_window_title", new_callable=AsyncMock, return_value=None):
        result = await agent.collect()

    assert result == []


# ── CommunicationAgent ────────────────────────────────────────────────────────

def test_communication_agent_name():
    db = AsyncMock()
    agent = CommunicationAgent(db)
    assert agent.agent_name == "communication"


@pytest.mark.asyncio
async def test_communication_agent_skips_without_token():
    db = AsyncMock()
    with patch.dict("os.environ", {"SLACK_BOT_TOKEN": "", "SLACK_CHANNELS": "C123"}):
        agent = CommunicationAgent(db)
    result = await agent.collect()
    assert result == []


@pytest.mark.asyncio
async def test_communication_agent_skips_without_channels():
    db = AsyncMock()
    with patch.dict("os.environ", {"SLACK_BOT_TOKEN": "xoxb-test", "SLACK_CHANNELS": ""}):
        agent = CommunicationAgent(db)
    result = await agent.collect()
    assert result == []
