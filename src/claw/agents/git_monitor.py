"""GitMonitorAgent — polls git log for new commits and branch changes."""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

from .base import BaseMonitorAgent

logger = logging.getLogger(__name__)


class GitMonitorAgent(BaseMonitorAgent):
    """Watches a git repository and logs commits as they happen."""

    agent_name = "git"

    def __init__(
        self,
        db: aiosqlite.Connection,
        repo_path: str | Path | None = None,
        poll_interval: int = 300,
    ) -> None:
        super().__init__(db, poll_interval)
        self._repo_path = Path(repo_path or os.environ.get("GIT_REPO_PATH", ".")).resolve()
        self._last_commit_hash: str | None = None

    async def collect(self) -> list[tuple[str, dict]]:
        try:
            import git  # gitpython
        except ImportError:
            logger.warning("gitpython not installed; git monitoring disabled")
            return []

        events: list[tuple[str, dict]] = []
        try:
            repo = await asyncio.to_thread(git.Repo, self._repo_path, search_parent_directories=True)
        except git.InvalidGitRepositoryError:
            logger.debug("No git repo found at %s", self._repo_path)
            return []

        # Collect new commits since last seen hash
        try:
            commits = await asyncio.to_thread(
                lambda: list(repo.iter_commits(max_count=20))
            )
        except Exception:
            return []

        new_commits: list[git.Commit] = []
        for commit in commits:
            if commit.hexsha == self._last_commit_hash:
                break
            new_commits.append(commit)

        if new_commits:
            self._last_commit_hash = commits[0].hexsha

        for commit in reversed(new_commits):
            payload = {
                "hash": commit.hexsha[:12],
                "message": commit.message.strip()[:200],
                "author": str(commit.author.name),
                "files_changed": len(commit.stats.files),
                "insertions": commit.stats.total.get("insertions", 0),
                "deletions": commit.stats.total.get("deletions", 0),
                "timestamp": datetime.fromtimestamp(commit.committed_date, tz=timezone.utc).isoformat(),
                "branch": self._current_branch(repo),
            }
            events.append(("commit", payload))
            logger.info("[git] new commit %s: %s", payload["hash"], payload["message"][:60])

        return events

    @staticmethod
    def _current_branch(repo) -> str:
        try:
            return repo.active_branch.name
        except TypeError:
            return "detached"
