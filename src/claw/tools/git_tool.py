"""NeMo Agent Toolkit tool: read git events from the event log."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from nat.builder.builder import Builder
from nat.builder.framework_enum import LLMFrameworkEnum
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.function import FunctionBaseConfig

from claw.database import get_db, get_events


class GitEventsToolConfig(FunctionBaseConfig, name="git_events_tool"):
    pass


@register_function(config_type=GitEventsToolConfig, framework_wrappers=[LLMFrameworkEnum.LANGCHAIN])
async def git_events_tool(_config: GitEventsToolConfig, _builder: Builder):
    async def _get_git_events(session_id: str = "") -> str:
        """Return git commit events for a session (YYYY-MM-DD). Defaults to today."""
        sid = session_id or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        db = await get_db(os.environ.get("DB_PATH", "data/claw.db"))
        try:
            events = await get_events(db, sid, agent="git")
        finally:
            await db.close()
        return json.dumps(events, default=str)

    yield FunctionInfo.from_fn(_get_git_events, description=_get_git_events.__doc__)
