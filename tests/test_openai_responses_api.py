"""OpenAI Responses API behavior tests — FU12 migrated.

Migration note (FU12, 2026-05-05): this suite previously patched
``components.agentic_lua_generator.requests.post`` to intercept the
in-tree HTTP calls inside the deleted legacy helpers
(``_call_openai_responses``, ``_call_openai_responses_raw``,
``_call_openai_chat_completions``). FU12 deleted those helpers along
with the ``requests`` import; production GPT-5 calls now flow through
the unified ``OpenAIProvider`` (``components/llm_provider.py``) which
uses the official ``openai`` SDK.

Migration choices:
  * Tests that exercised the raw HTTP shape were rewritten to mock the
    AsyncOpenAI client at ``provider._client`` and assert which API
    surface (``responses.create`` vs ``chat.completions.create``) the
    provider hit. Same behaviour, new patch surface.
  * Tests for OPENAI_REASONING_EFFORT / OPENAI_TEXT_VERBOSITY pass-through
    moved to tests/test_llm_provider_openai_responses.py — DA-FU12 caught
    the regression where the unified provider wasn't forwarding those env
    vars after the helper deletion. They are now wired through
    ``OpenAIProvider._agenerate_once_responses`` and pinned by tests in
    the new suite.
  * The ``_normalize_openai_reasoning_effort`` unit test stays put — the
    normalizer function relocated to ``components/llm_provider.py`` but
    is re-exported from ``components/agentic_lua_generator.py`` for
    back-compat with this import.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from components.agentic_lua_generator import _normalize_openai_reasoning_effort
from components.llm_provider import OpenAIProvider


def _run(coro):
    return asyncio.run(coro)


def _make_chat_response():
    """Returns a fake chat.completions.create response with text 'ok'."""
    class FakeUsage:
        prompt_tokens = 10
        completion_tokens = 5

    class FakeMessage:
        content = "ok"

    class FakeChoice:
        message = FakeMessage()
        finish_reason = "stop"

    class FakeResponse:
        choices = [FakeChoice()]
        usage = FakeUsage()

    return FakeResponse()


def _make_responses_response(text: str = "ok", *, output_text: bool = True):
    """Returns a fake responses.create response.

    If output_text=True, sets the convenience .output_text attribute (the
    SDK's preferred extraction path). Else leaves it None and returns the
    text via the .output[].content[].text walk fallback.
    """
    class FakeRespUsage:
        input_tokens = 10
        output_tokens = 5
        input_tokens_details = None

    class FakeBlock:
        def __init__(self, t: str) -> None:
            self.text = t
            self.type = "output_text"

    class FakeOutputItem:
        def __init__(self, blocks):
            self.content = blocks

    class FakeResponse:
        id = "resp_test_abc"
        usage = FakeRespUsage()
        incomplete_details = None

    response = FakeResponse()
    if output_text:
        response.output_text = text
        response.output = []
    else:
        response.output_text = None
        response.output = [FakeOutputItem([FakeBlock(text)])]
    return response


def _make_fake_client(*, chat_create=None, responses_create=None):
    """Build an AsyncOpenAI-shaped MagicMock with the requested async stubs."""
    client = MagicMock()
    client.chat = MagicMock()
    client.chat.completions = MagicMock()
    client.responses = MagicMock()

    if chat_create is None:
        async def chat_create(**kwargs):  # noqa: F811
            return _make_chat_response()
    if responses_create is None:
        async def responses_create(**kwargs):  # noqa: F811
            return _make_responses_response()

    client.chat.completions.create = chat_create
    client.responses.create = responses_create
    return client


def test_gpt5_routes_to_responses_api(monkeypatch):
    """gpt-5* routes through client.responses.create (NOT chat.completions)."""
    monkeypatch.delenv("OPENAI_API_MODE", raising=False)

    chat_calls: list = []

    async def chat_create(**kwargs):
        chat_calls.append(kwargs)
        return _make_chat_response()

    captured: dict = {}

    async def responses_create(**kwargs):
        captured.update(kwargs)
        return _make_responses_response("function processEvent(event)\n  return event\nend")

    OpenAIProvider._NO_TEMPERATURE_DISCOVERED.clear()
    OpenAIProvider._NO_MAX_TOKENS_DISCOVERED.clear()
    provider = OpenAIProvider(api_key="test-key")
    provider._client = _make_fake_client(
        chat_create=chat_create, responses_create=responses_create,
    )

    resp = _run(
        provider.agenerate(
            system="instructions text",
            messages=[{"role": "user", "content": "Generate Lua"}],
            model="gpt-5.2",
            max_tokens=4096,
        )
    )

    assert resp.text == "function processEvent(event)\n  return event\nend"
    # Routed correctly: chat path NOT used.
    assert chat_calls == []
    # Routed correctly: responses path used with the right shape.
    assert captured["model"] == "gpt-5.2"
    assert captured["instructions"] == "instructions text"
    assert captured["input"] == [{"role": "user", "content": "Generate Lua"}]
    assert captured["max_output_tokens"] == 4096


def test_responses_api_extracts_nested_output(monkeypatch):
    """When the SDK returns no .output_text, walk .output[].content[].text."""
    monkeypatch.setenv("OPENAI_API_MODE", "responses")

    async def responses_create(**kwargs):
        return _make_responses_response(
            "function processEvent(event)\n  return event\nend",
            output_text=False,
        )

    OpenAIProvider._NO_TEMPERATURE_DISCOVERED.clear()
    OpenAIProvider._NO_MAX_TOKENS_DISCOVERED.clear()
    provider = OpenAIProvider(api_key="test-key")
    provider._client = _make_fake_client(responses_create=responses_create)

    resp = _run(
        provider.agenerate(
            system="sys",
            messages=[{"role": "user", "content": "Generate Lua"}],
            model="gpt-4o-mini",
        )
    )

    assert resp.text == "function processEvent(event)\n  return event\nend"


def test_gpt4o_uses_chat_completions_by_default(monkeypatch):
    """gpt-4o is NOT in the Responses API prefix list -> chat.completions."""
    monkeypatch.delenv("OPENAI_API_MODE", raising=False)

    captured: dict = {}

    async def chat_create(**kwargs):
        captured.update(kwargs)
        return _make_chat_response()

    responses_calls: list = []

    async def responses_create(**kwargs):
        responses_calls.append(kwargs)
        return _make_responses_response()

    OpenAIProvider._NO_TEMPERATURE_DISCOVERED.clear()
    OpenAIProvider._NO_MAX_TOKENS_DISCOVERED.clear()
    provider = OpenAIProvider(api_key="test-key")
    provider._client = _make_fake_client(
        chat_create=chat_create, responses_create=responses_create,
    )

    resp = _run(
        provider.agenerate(
            system="sys-prompt",
            messages=[{"role": "user", "content": "Generate Lua"}],
            model="gpt-4o-mini",
        )
    )

    assert resp.text == "ok"
    assert responses_calls == []
    # Chat completions: messages start with the system prompt entry.
    assert captured["model"] == "gpt-4o-mini"
    assert captured["messages"][0] == {"role": "system", "content": "sys-prompt"}


def test_api_mode_override_can_force_responses_for_older_models(monkeypatch):
    """OPENAI_API_MODE=responses forces gpt-4o through the Responses API."""
    monkeypatch.setenv("OPENAI_API_MODE", "responses")

    chat_calls: list = []

    async def chat_create(**kwargs):
        chat_calls.append(kwargs)
        return _make_chat_response()

    captured: dict = {}

    async def responses_create(**kwargs):
        captured.update(kwargs)
        return _make_responses_response()

    OpenAIProvider._NO_TEMPERATURE_DISCOVERED.clear()
    OpenAIProvider._NO_MAX_TOKENS_DISCOVERED.clear()
    provider = OpenAIProvider(api_key="test-key")
    provider._client = _make_fake_client(
        chat_create=chat_create, responses_create=responses_create,
    )

    resp = _run(
        provider.agenerate(
            system="sys",
            messages=[{"role": "user", "content": "Generate Lua"}],
            model="gpt-4o-mini",
        )
    )

    assert resp.text == "ok"
    assert chat_calls == []
    assert captured["model"] == "gpt-4o-mini"


def test_api_mode_override_can_force_chat_for_gpt5(monkeypatch):
    """OPENAI_API_MODE=chat forces gpt-5 onto chat.completions."""
    monkeypatch.setenv("OPENAI_API_MODE", "chat")

    captured: dict = {}

    async def chat_create(**kwargs):
        captured.update(kwargs)
        return _make_chat_response()

    responses_calls: list = []

    async def responses_create(**kwargs):
        responses_calls.append(kwargs)
        return _make_responses_response()

    OpenAIProvider._NO_TEMPERATURE_DISCOVERED.clear()
    OpenAIProvider._NO_MAX_TOKENS_DISCOVERED.clear()
    provider = OpenAIProvider(api_key="test-key")
    provider._client = _make_fake_client(
        chat_create=chat_create, responses_create=responses_create,
    )

    resp = _run(
        provider.agenerate(
            system="sys",
            messages=[{"role": "user", "content": "Generate Lua"}],
            model="gpt-5-mini",
        )
    )

    assert resp.text == "ok"
    assert responses_calls == []
    assert captured["model"] == "gpt-5-mini"


def test_reasoning_effort_normalizer_preserves_none_for_gpt_5_1():
    """Pure unit test of _normalize_openai_reasoning_effort — unaffected by FU12."""
    assert _normalize_openai_reasoning_effort("gpt-5.1", "none") == ("none", None)


def test_openai_responses_logs_http_error_body(monkeypatch, tmp_path: Path, caplog):
    """Verify the SDK adapter on AgenticLuaGenerator surfaces the SDK's error.

    Replaces the deleted requests.post-based test. Uses the SDK adapter
    method (_call_openai_responses_via_sdk) with a stubbed provider that
    raises, asserting the {"text":None,"response_id":None,"data":None}
    fallback shape AND that the error message is logged.
    """
    from components.agentic_lua_generator import AgenticLuaGenerator

    gen = AgenticLuaGenerator(
        api_key="test-key",
        model="gpt-5-mini",
        provider="openai",
        output_dir=tmp_path,
    )

    class _StubProvider:
        def generate(self, **kwargs: Any) -> Any:
            raise RuntimeError("400 Client Error: bad request details")

    # Force the inner provider to our stub by overriding the property's cache.
    gen._inner._provider_override = _StubProvider()  # type: ignore[assignment]

    caplog.set_level("ERROR")
    result = gen._call_openai_responses_via_sdk(
        model="gpt-5-mini",
        instructions="test",
        input_items=[{"role": "user", "content": "test"}],
    )

    assert result == {"text": None, "response_id": None, "data": None}
    assert "bad request details" in caplog.text
