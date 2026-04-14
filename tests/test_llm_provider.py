"""Phase 3.A + 3.B + 3.C tests for components.llm_provider."""
import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestModuleImportIsLight:
    def test_no_heavy_imports_at_module_load(self):
        """Importing llm_provider must NOT load anthropic/openai/google.generativeai."""
        import sys
        # Reset
        for mod in list(sys.modules):
            if mod.startswith(("components.llm_provider", "anthropic", "openai", "google.generativeai")):
                if mod in sys.modules:
                    del sys.modules[mod]
        import components.llm_provider  # noqa: F401
        heavy = [m for m in ("anthropic", "openai", "google.generativeai") if m in sys.modules]
        assert heavy == [], f"llm_provider.py leaked heavy deps at module load: {heavy}"


class TestLLMResponseDataclass:
    def test_default_fields(self):
        from components.llm_provider import LLMResponse
        r = LLMResponse(text="hi", model="test-model")
        assert r.text == "hi"
        assert r.model == "test-model"
        assert r.usage == {}
        assert r.cache_read_input_tokens == 0
        assert r.provider == ""


class TestProviderProtocol:
    def test_runtime_checkable(self):
        from components.llm_provider import LLMProvider, AnthropicProvider
        # runtime_checkable Protocol means isinstance check works
        p = AnthropicProvider(api_key="test")
        assert isinstance(p, LLMProvider)

    def test_all_three_providers_have_name(self):
        from components.llm_provider import AnthropicProvider, OpenAIProvider, GeminiProvider
        assert AnthropicProvider(api_key="x").name == "anthropic"
        assert OpenAIProvider(api_key="x").name == "openai"
        assert GeminiProvider(api_key="x").name == "gemini"


class TestFactory:
    def test_get_provider_anthropic(self):
        from components.llm_provider import get_provider, AnthropicProvider
        p = get_provider("anthropic", api_key="test")
        assert isinstance(p, AnthropicProvider)

    def test_get_provider_openai(self):
        from components.llm_provider import get_provider, OpenAIProvider
        p = get_provider("openai", api_key="test")
        assert isinstance(p, OpenAIProvider)

    def test_get_provider_gemini(self):
        from components.llm_provider import get_provider, GeminiProvider
        p = get_provider("gemini", api_key="test")
        assert isinstance(p, GeminiProvider)

    def test_get_provider_default_uses_env(self, monkeypatch):
        from components.llm_provider import get_provider, AnthropicProvider, OpenAIProvider
        monkeypatch.setenv("LLM_PROVIDER_PREFERENCE", "openai")
        p = get_provider("default", api_key="test")
        assert isinstance(p, OpenAIProvider)

    def test_get_provider_unknown_raises(self):
        from components.llm_provider import get_provider
        with pytest.raises(ValueError, match="unknown provider"):
            get_provider("llama", api_key="test")


class TestSyncWrapperFailsFastInLoop:
    def test_generate_outside_loop_works_with_mock(self):
        """Sync generate() should call agenerate via asyncio.run when no loop is running."""
        from components.llm_provider import AnthropicProvider, LLMResponse

        p = AnthropicProvider(api_key="test")
        fake = LLMResponse(text="mocked", model="test-model")

        async def fake_agenerate(*args, **kwargs):
            return fake

        p.agenerate = fake_agenerate  # monkeypatch
        result = p.generate(system="s", messages=[], model="test-model")
        assert result.text == "mocked"

    def test_generate_inside_loop_raises(self):
        from components.llm_provider import AnthropicProvider

        p = AnthropicProvider(api_key="test")

        async def caller():
            with pytest.raises(RuntimeError, match="running event loop"):
                p.generate(system="s", messages=[], model="test-model")

        asyncio.run(caller())


class TestAnthropicPromptCachingShape:
    """Phase 3.B: when cache_breakpoints=True, system must be a list with cache_control."""

    def test_system_block_has_cache_control(self):
        """Verify the outbound `system` argument shape by inspecting the mocked client call."""
        from components.llm_provider import AnthropicProvider

        p = AnthropicProvider(api_key="test")

        # Mock the client's messages.create to capture the args
        captured = {}

        class FakeUsage:
            input_tokens = 100
            output_tokens = 50
            cache_read_input_tokens = 0

        class FakeBlock:
            type = "text"
            text = "hello"

        class FakeResponse:
            content = [FakeBlock()]
            usage = FakeUsage()
            stop_reason = "end_turn"

        async def fake_create(**kwargs):
            captured.update(kwargs)
            return FakeResponse()

        class FakeMessages:
            create = staticmethod(fake_create)

        class FakeClient:
            messages = FakeMessages()

        p._client = FakeClient()

        async def run():
            return await p.agenerate(
                system="You are a helpful assistant.",
                messages=[{"role": "user", "content": "hi"}],
                model="claude-haiku-4-5-20251001",
                cache_breakpoints=True,
            )

        resp = asyncio.run(run())
        # system must be a list with one block carrying cache_control
        assert isinstance(captured["system"], list)
        assert captured["system"][0]["type"] == "text"
        assert captured["system"][0]["text"] == "You are a helpful assistant."
        assert captured["system"][0]["cache_control"] == {"type": "ephemeral"}
        # response text extracted correctly
        assert resp.text == "hello"

    def test_system_plain_string_when_cache_disabled(self):
        from components.llm_provider import AnthropicProvider

        p = AnthropicProvider(api_key="test")
        captured = {}

        class FakeBlock:
            type = "text"
            text = "hi"

        class FakeResponse:
            content = [FakeBlock()]
            usage = None
            stop_reason = "end_turn"

        async def fake_create(**kwargs):
            captured.update(kwargs)
            return FakeResponse()

        p._client = MagicMock()
        p._client.messages = MagicMock()
        p._client.messages.create = fake_create

        async def run():
            return await p.agenerate(
                system="plain system",
                messages=[{"role": "user", "content": "hi"}],
                model="claude-haiku-4-5-20251001",
                cache_breakpoints=False,
            )

        asyncio.run(run())
        assert captured["system"] == "plain system"  # plain string when cache disabled


class TestRetryBackoff:
    """Retries on transient errors, raises on permanent errors."""

    def test_retriable_error_retries(self):
        from components.llm_provider import AnthropicProvider, LLMProviderError, LLMResponse

        attempts = {"count": 0}

        async def flaky(*a, **kw):
            attempts["count"] += 1
            if attempts["count"] < 2:
                raise LLMProviderError("transient")
            return LLMResponse(text="ok", model="m")

        p = AnthropicProvider(api_key="test")
        p._agenerate_once = flaky

        result = asyncio.run(p.agenerate(system="", messages=[], model="m"))
        assert result.text == "ok"
        assert attempts["count"] == 2

    def test_permanent_error_raises(self):
        from components.llm_provider import AnthropicProvider, LLMProviderPermanentError

        async def always_permanent(*a, **kw):
            raise LLMProviderPermanentError("bad key")

        p = AnthropicProvider(api_key="test")
        p._agenerate_once = always_permanent

        with pytest.raises(LLMProviderPermanentError):
            asyncio.run(p.agenerate(system="", messages=[], model="m"))


class TestModelIdRefresh:
    """Phase 3.C: grep-based CI gate for stale model IDs."""

    def test_no_claude_3_ids_in_production(self):
        import re
        from pathlib import Path
        repo = Path(__file__).resolve().parent.parent
        stale_pattern = re.compile(r"claude-3-(?:5-)?(?:haiku|sonnet|opus)-20\d{6}")
        allowed_dirs = ["components", "orchestrator", "services", "scripts"]
        # Env/yaml files also:
        extra_files = [".env.example", "docker-compose.yml", "config.yaml.example"]
        hits = []
        for d in allowed_dirs:
            for p in (repo / d).rglob("*.py"):
                try:
                    text = p.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue
                for m in stale_pattern.finditer(text):
                    hits.append((p.relative_to(repo).as_posix(), m.group(0)))
        for f in extra_files:
            fp = repo / f
            if fp.exists():
                try:
                    text = fp.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue
                for m in stale_pattern.finditer(text):
                    hits.append((f, m.group(0)))
        assert not hits, f"Stale claude-3 model IDs found: {hits}"
