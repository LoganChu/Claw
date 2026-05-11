"""Unit tests for the privacy filter guardrail."""
import pytest
from claw.safety import scrub_payload, scrub_string


def test_scrub_api_key_in_string():
    raw = "OPENAI_API_KEY=sk-abc123def456ghi789jkl012mno345pqr678"
    result = scrub_string(raw)
    assert "sk-" not in result
    assert "[REDACTED]" in result


def test_scrub_github_pat():
    raw = "token: ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcde1234"
    result = scrub_string(raw)
    assert "ghp_" not in result


def test_scrub_nested_dict():
    payload = {
        "message": "fix bug",
        "author": "Logan",
        "env": {"GITHUB_TOKEN": "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcde1234"},
    }
    result = scrub_payload(payload)
    assert "ghp_" not in str(result)
    assert result["message"] == "fix bug"
    assert result["author"] == "Logan"


def test_scrub_list():
    payload = ["normal string", "api_key: sk-something123456789012345678901234"]
    result = scrub_payload(payload)
    assert "sk-" not in str(result)
    assert result[0] == "normal string"


def test_clean_payload_unchanged():
    payload = {"hash": "abc123", "message": "Add feature", "files_changed": 3}
    result = scrub_payload(payload)
    assert result == payload
