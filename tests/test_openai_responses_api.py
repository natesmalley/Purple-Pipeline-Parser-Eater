from pathlib import Path

import pytest
import requests

# Merge-resolution OOS-2 (2026-04-27): `_normalize_openai_reasoning_effort`
# is part of upstream's GPT-5 / Responses-API tuning support that didn't
# survive our Stream 3.G hollowing. See OOS tracker.
pytestmark = pytest.mark.skip(
    reason="OOS-2: OpenAI Responses-API + reasoning-effort tuning deferred."
)

try:
    from components.agentic_lua_generator import (
        AgenticLuaGenerator,
        SYSTEM_PROMPT,
        _normalize_openai_reasoning_effort,
    )
except ImportError:
    AgenticLuaGenerator = None  # type: ignore[assignment,misc]
    SYSTEM_PROMPT = None  # type: ignore[assignment]
    _normalize_openai_reasoning_effort = None  # type: ignore[assignment]


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_gpt5_uses_responses_api_with_gpt5_options(monkeypatch, tmp_path: Path):
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return _FakeResponse({"output_text": "function processEvent(event)\n  return event\nend"})

    monkeypatch.delenv("OPENAI_API_MODE", raising=False)
    monkeypatch.setenv("OPENAI_REASONING_EFFORT", "low")
    monkeypatch.setenv("OPENAI_TEXT_VERBOSITY", "medium")
    monkeypatch.setattr("components.agentic_lua_generator.requests.post", fake_post)

    gen = AgenticLuaGenerator(
        api_key="test-key",
        model="gpt-5.2",
        provider="openai",
        output_dir=tmp_path,
    )

    result = gen._call_openai([{"role": "user", "content": "Generate Lua"}], "gpt-5.2")

    assert result == "function processEvent(event)\n  return event\nend"
    assert captured["url"] == "https://api.openai.com/v1/responses"
    assert captured["json"]["model"] == "gpt-5.2"
    assert captured["json"]["instructions"] == SYSTEM_PROMPT
    assert captured["json"]["input"] == [{"role": "user", "content": "Generate Lua"}]
    assert captured["json"]["reasoning"] == {"effort": "low"}
    assert captured["json"]["text"] == {"verbosity": "medium"}


def test_openai_responses_can_extract_nested_output(monkeypatch, tmp_path: Path):
    def fake_post(url, headers=None, json=None, timeout=None):
        return _FakeResponse(
            {
                "output": [
                    {
                        "content": [
                            {"type": "output_text", "text": "function processEvent(event)\n  return event\nend"}
                        ]
                    }
                ]
            }
        )

    monkeypatch.setenv("OPENAI_API_MODE", "responses")
    monkeypatch.setattr("components.agentic_lua_generator.requests.post", fake_post)

    gen = AgenticLuaGenerator(
        api_key="test-key",
        model="gpt-4o-mini",
        provider="openai",
        output_dir=tmp_path,
    )

    result = gen._call_openai([{"role": "user", "content": "Generate Lua"}], "gpt-4o-mini")

    assert result == "function processEvent(event)\n  return event\nend"


def test_gpt4o_uses_chat_completions_by_default(monkeypatch, tmp_path: Path):
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return _FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": "function processEvent(event)\n  return event\nend"
                        }
                    }
                ]
            }
        )

    monkeypatch.delenv("OPENAI_API_MODE", raising=False)
    monkeypatch.setattr("components.agentic_lua_generator.requests.post", fake_post)

    gen = AgenticLuaGenerator(
        api_key="test-key",
        model="gpt-4o-mini",
        provider="openai",
        output_dir=tmp_path,
    )

    result = gen._call_openai([{"role": "user", "content": "Generate Lua"}], "gpt-4o-mini")

    assert result == "function processEvent(event)\n  return event\nend"
    assert captured["url"] == "https://api.openai.com/v1/chat/completions"
    assert captured["json"]["messages"][0] == {"role": "system", "content": SYSTEM_PROMPT}


def test_api_mode_override_can_force_responses_for_older_models(monkeypatch, tmp_path: Path):
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        return _FakeResponse({"output_text": "ok"})

    monkeypatch.setenv("OPENAI_API_MODE", "responses")
    monkeypatch.setattr("components.agentic_lua_generator.requests.post", fake_post)

    gen = AgenticLuaGenerator(
        api_key="test-key",
        model="gpt-4o-mini",
        provider="openai",
        output_dir=tmp_path,
    )

    result = gen._call_openai([{"role": "user", "content": "Generate Lua"}], "gpt-4o-mini")

    assert result == "ok"
    assert captured["url"] == "https://api.openai.com/v1/responses"


def test_gpt5_none_reasoning_effort_is_downgraded_for_pre_51_models(monkeypatch, tmp_path: Path):
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["json"] = json
        return _FakeResponse({"output_text": "ok"})

    monkeypatch.delenv("OPENAI_API_MODE", raising=False)
    monkeypatch.setenv("OPENAI_REASONING_EFFORT", "none")
    monkeypatch.setenv("OPENAI_TEXT_VERBOSITY", "medium")
    monkeypatch.setattr("components.agentic_lua_generator.requests.post", fake_post)

    gen = AgenticLuaGenerator(
        api_key="test-key",
        model="gpt-5-mini",
        provider="openai",
        output_dir=tmp_path,
    )

    result = gen._call_openai([{"role": "user", "content": "Generate Lua"}], "gpt-5-mini")

    assert result == "ok"
    assert captured["json"]["reasoning"] == {"effort": "minimal"}


def test_reasoning_effort_normalizer_preserves_none_for_gpt_5_1():
    assert _normalize_openai_reasoning_effort("gpt-5.1", "none") == ("none", None)


def test_openai_responses_logs_http_error_body(monkeypatch, tmp_path: Path, caplog):
    class _ErrorResponse:
        text = '{"error":{"message":"bad request details"}}'

    def fake_post(url, headers=None, json=None, timeout=None):
        err = requests.HTTPError("400 Client Error")
        err.response = _ErrorResponse()
        raise err

    monkeypatch.setattr("components.agentic_lua_generator.requests.post", fake_post)

    gen = AgenticLuaGenerator(
        api_key="test-key",
        model="gpt-5-mini",
        provider="openai",
        output_dir=tmp_path,
    )

    caplog.set_level("ERROR")
    result = gen._call_openai_responses_raw(
        model="gpt-5-mini",
        instructions="test",
        input_items=[{"role": "user", "content": "test"}],
    )

    assert result == {"text": None, "response_id": None, "data": None}
    assert 'bad request details' in caplog.text
