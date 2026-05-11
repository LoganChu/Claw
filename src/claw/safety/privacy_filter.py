"""
Guardrail: strip credentials, tokens, and PII from event payloads before storage.
Runs on every payload before it hits the database.
"""
from __future__ import annotations

import re
from typing import Any


# Patterns that look like secrets — value is replaced with a safe sentinel
_SECRET_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(?i)(api[_-]?key|token|secret|password|passwd|auth|bearer)\s*[:=]\s*\S+"),
    re.compile(r"ghp_[A-Za-z0-9]{10,}"),        # GitHub PAT (classic: 40 chars, fine-grained: longer)
    re.compile(r"sk-[A-Za-z0-9]{32,}"),         # OpenAI-style key
    re.compile(r"xoxb-[A-Za-z0-9\-]+"),          # Slack bot token
    re.compile(r"(?<!\w)\d{3}[-.\s]?\d{2}[-.\s]?\d{4}(?!\d)"),  # SSN-like
]

_REDACTED = "[REDACTED]"


def scrub_string(value: str) -> str:
    for pattern in _SECRET_PATTERNS:
        value = pattern.sub(_REDACTED, value)
    return value


def scrub_payload(payload: Any) -> Any:
    """Recursively redact secrets from any JSON-serialisable structure."""
    if isinstance(payload, str):
        return scrub_string(payload)
    if isinstance(payload, dict):
        return {k: scrub_payload(v) for k, v in payload.items()}
    if isinstance(payload, list):
        return [scrub_payload(item) for item in payload]
    return payload
