"""NeMo Agent Toolkit tool: query historical productivity summaries."""
from __future__ import annotations

import json
import os

from nat.builder.builder import Builder
from nat.builder.framework_enum import LLMFrameworkEnum
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.function import FunctionBaseConfig

from claw.database import get_db, get_recent_summaries


class ProductivityHistoryToolConfig(FunctionBaseConfig, name="productivity_history_tool"):
    pass


@register_function(config_type=ProductivityHistoryToolConfig, framework_wrappers=[LLMFrameworkEnum.LANGCHAIN])
async def productivity_history_tool(_config: ProductivityHistoryToolConfig, _builder: Builder):
    async def _get_history(days: int = 14) -> str:
        """Return productivity summaries for the last N days (default 14)."""
        db = await get_db(os.environ.get("DB_PATH", "data/claw.db"))
        try:
            summaries = await get_recent_summaries(db, days=days)
        finally:
            await db.close()
        # Drop the full report_md to keep token count reasonable
        slim = [{k: v for k, v in s.items() if k != "report_md"} for s in summaries]
        return json.dumps(slim, default=str)

    yield FunctionInfo.from_fn(_get_history, description=_get_history.__doc__)
