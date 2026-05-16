"""NeMo Agent Toolkit tool: apply privacy filter to a payload dict."""
from __future__ import annotations

import json

from nat.builder.builder import Builder
from nat.builder.framework_enum import LLMFrameworkEnum
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.function import FunctionBaseConfig

from claw.safety import scrub_payload


class PrivacyFilterToolConfig(FunctionBaseConfig, name="privacy_filter_tool"):
    pass


@register_function(config_type=PrivacyFilterToolConfig, framework_wrappers=[LLMFrameworkEnum.LANGCHAIN])
async def privacy_filter_tool(_config: PrivacyFilterToolConfig, _builder: Builder):
    async def _apply_privacy_filter(payload_json: str) -> str:
        """Scrub secrets (API keys, tokens, passwords) from a JSON payload string. Returns scrubbed JSON."""
        try:
            payload = json.loads(payload_json)
        except json.JSONDecodeError:
            return json.dumps({"error": "invalid JSON input"})
        return json.dumps(scrub_payload(payload), default=str)

    yield FunctionInfo.from_fn(_apply_privacy_filter, description=_apply_privacy_filter.__doc__)
