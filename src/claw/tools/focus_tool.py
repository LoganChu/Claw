"""NeMo Agent Toolkit tool: read focus/window events from the event log."""
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


class FocusEventsToolConfig(FunctionBaseConfig, name="focus_events_tool"):
    pass


@register_function(config_type=FocusEventsToolConfig, framework_wrappers=[LLMFrameworkEnum.LANGCHAIN])
async def focus_events_tool(_config: FocusEventsToolConfig, _builder: Builder):
    async def _get_focus_events(session_id: str = "") -> str:
        """Return focus/distraction window events for a session (YYYY-MM-DD)."""
        sid = session_id or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        db = await get_db(os.environ.get("DB_PATH", "data/claw.db"))
        try:
            events = await get_events(db, sid, agent="focus")
        finally:
            await db.close()
        return json.dumps(events, default=str)

    yield FunctionInfo.from_fn(_get_focus_events, description=_get_focus_events.__doc__)
