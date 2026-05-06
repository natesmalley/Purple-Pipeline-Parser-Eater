"""FU15 P1-3 + DA-Arch FU10 follow-up — Gemini context caching + typed signature.

All MOCKED. No live API calls.

Two concerns exercised here:

  P1-3  ``GeminiProvider._agenerate_once`` must use the documented legacy
        ``google-generativeai`` two-step caching pattern:

            cached = genai.caching.CachedContent.create(
                model=model, system_instruction=system, ttl="5m",
            )
            model_obj = genai.GenerativeModel.from_cached_content(
                cached_content=cached,
                generation_config=..., safety_settings=...,
            )

        NOT the keyword form
        ``GenerativeModel(model_name=..., cached_content=...)`` —
        that's a different API surface.

        ``system_instruction=`` must NOT be passed to ``from_cached_content``
        (the system content is already baked into the cache, the SDK rejects
        duplicates).

        Skip caching for short systems (< 4096 chars) and when
        ``cache_breakpoints=False``. Cache failure (create OR
        from_cached_content) must NEVER block the call — log WARNING and
        fall back to the existing uncached path.

  DA    DA-Architecture FU10 follow-up: ``GeminiProvider.agenerate`` exposes
        the explicit typed signature matching ``AnthropicProvider`` /
        ``OpenAIProvider`` (system, messages, model, max_tokens, temperature,
        cache_breakpoints, messages_split, previous_response_id,
        response_format), not the previous ``*args, **kwargs`` form.

Mocking strategy: tests inject a fake ``google.generativeai`` shape at
``provider._genai`` so ``_ensure_client()`` short-circuits without importing
the real SDK. We read ``call_args.kwargs`` on the SDK mocks to assert which
params landed where (CachedContent.create vs GenerativeModel(...) vs
from_cached_content).

Test-order safety: every test does a late-bound
``from components import llm_provider as mod`` (via ``_live_module()``) so
a re-import in a sibling test file (TestModuleImportIsLight in
``test_llm_provider.py``) doesn't strand our references on a stale module
object. See ``test_llm_provider_anthropic_thinking.py``'s ``_live_module()``
docstring for the full rationale.
"""
from __future__ import annotations

import asyncio
import inspect
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(coro):
    return asyncio.run(coro)


def _live_module():
    """Return the CURRENT ``components.llm_provider`` module object.

    Late-bound for the same reason as the FU13/FU14 helpers — see the
    docstring on the helper of the same name in
    ``test_llm_provider_anthropic_thinking.py``.
    """
    import importlib
    return importlib.import_module("components.llm_provider")


class _FakeUsageMetadata:
    """Mimic ``response.usage_metadata`` from google-generativeai."""

    def __init__(
        self,
        prompt_token_count: int = 100,
        candidates_token_count: int = 50,
        cached_content_token_count: int = 0,
    ):
        self.prompt_token_count = prompt_token_count
        self.candidates_token_count = candidates_token_count
        self.cached_content_token_count = cached_content_token_count


class _FakeCandidate:
    finish_reason = "STOP"


class _FakeGeminiResponse:
    """Mimic the shape of ``GenerativeModel.generate_content``'s result."""

    def __init__(
        self,
        text: str = "ok",
        cached_content_token_count: int = 0,
    ):
        self._text = text
        self.candidates = [_FakeCandidate()]
        self.usage_metadata = _FakeUsageMetadata(
            cached_content_token_count=cached_content_token_count,
        )

    @property
    def text(self):
        return self._text


def _make_fake_genai(
    *,
    cache_create_raises: Optional[Exception] = None,
    from_cached_raises: Optional[Exception] = None,
    cached_content_token_count: int = 0,
    response_text: str = "ok",
):
    """Build a fake ``google.generativeai`` module with mocks we can assert on.

    Returns ``(genai, mocks)`` where ``mocks`` is a dict of references the
    tests use directly (``CachedContent.create``, ``GenerativeModel``,
    ``from_cached_content``, plus the model-instance mocks that get
    ``generate_content`` invoked on them).
    """
    genai = MagicMock(name="genai")

    # CachedContent.create
    cached_obj = MagicMock(name="cached_obj")
    cached_obj.name = "cachedContents/abc123"

    cached_content_create = MagicMock(name="CachedContent.create")
    if cache_create_raises is not None:
        cached_content_create.side_effect = cache_create_raises
    else:
        cached_content_create.return_value = cached_obj
    genai.caching = MagicMock(name="caching")
    genai.caching.CachedContent = MagicMock(name="CachedContent")
    genai.caching.CachedContent.create = cached_content_create

    # Model instance returned by both code paths.
    cached_model_instance = MagicMock(name="cached_model_instance")
    cached_model_instance.generate_content = MagicMock(
        return_value=_FakeGeminiResponse(
            text=response_text,
            cached_content_token_count=cached_content_token_count,
        )
    )

    uncached_model_instance = MagicMock(name="uncached_model_instance")
    uncached_model_instance.generate_content = MagicMock(
        return_value=_FakeGeminiResponse(
            text=response_text,
            cached_content_token_count=0,
        )
    )

    # GenerativeModel callable (constructor) returns the uncached instance.
    generative_model = MagicMock(
        name="GenerativeModel",
        return_value=uncached_model_instance,
    )

    # from_cached_content classmethod returns the cached instance unless
    # configured to raise.
    if from_cached_raises is not None:
        generative_model.from_cached_content = MagicMock(
            side_effect=from_cached_raises,
        )
    else:
        generative_model.from_cached_content = MagicMock(
            return_value=cached_model_instance,
        )

    genai.GenerativeModel = generative_model

    # configure() is called by _ensure_client; record but no-op.
    genai.configure = MagicMock()

    mocks = {
        "genai": genai,
        "cached_content_create": cached_content_create,
        "cached_obj": cached_obj,
        "GenerativeModel": generative_model,
        "from_cached_content": generative_model.from_cached_content,
        "cached_model_instance": cached_model_instance,
        "uncached_model_instance": uncached_model_instance,
    }
    return genai, mocks


def _new_provider(genai_mock):
    """Construct a GeminiProvider with the SDK mock pre-injected.

    Clears the class-level cache indices first so prior tests can't bleed in.
    FU16 added the ``_generative_model_cache_index`` dict alongside the
    FU15 ``_context_cache_index``; both must be cleared per test or a
    cached ``GenerativeModel`` from an earlier test would mask the
    construction this test is asserting on.
    """
    GeminiProvider = _live_module().GeminiProvider
    GeminiProvider._context_cache_index.clear()
    # ``getattr`` keeps this helper backward-compatible if the FU16 attr
    # is ever rolled back — present-and-empty is the common-case state.
    model_index = getattr(
        GeminiProvider, "_generative_model_cache_index", None,
    )
    if model_index is not None:
        model_index.clear()
    provider = GeminiProvider(api_key="test-key")
    provider._genai = genai_mock
    return provider


def _long_system(min_chars: int = 5000) -> str:
    """Return a system prompt long enough to clear the 2.5-flash caching threshold.

    Default 5000 chars ≥ 4096 (the per-model min for ``gemini-2.5-flash``,
    looked up via ``GeminiProvider._gemini_cache_min_chars``). Guard against
    accidental copy-paste shrinkage by computing length explicitly — if
    someone bumps the threshold upstream we fail loudly here rather than
    silently dropping below it.

    For tests targeting ``gemini-2.5-pro`` (threshold 8192) or unknown
    models (default 8192), pass ``min_chars=8500`` or higher.
    """
    base = (
        "You are an expert OCSF Lua transform generator. "
        "Apply patterns A-E. Inline OCSF helpers. "
    )
    n = (min_chars // len(base)) + 1
    out = base * n
    assert len(out) >= min_chars, "test helper produced too-short system"
    return out


# ---------------------------------------------------------------------------
# P1-3 — context cache create + reuse + expiry
# ---------------------------------------------------------------------------


class TestContextCacheCreatedOnFirstCall:
    def test_context_cache_created_on_first_call_with_long_system(self):
        genai, mocks = _make_fake_genai(cached_content_token_count=0)
        provider = _new_provider(genai)
        long_system = _long_system()

        _run(
            provider.agenerate(
                system=long_system,
                messages=[{"role": "user", "content": "hi"}],
                model="gemini-2.5-flash",
                max_tokens=4096,
                temperature=0.0,
                cache_breakpoints=True,
            )
        )

        # CachedContent.create called exactly once with documented kwargs.
        mocks["cached_content_create"].assert_called_once()
        ckwargs = mocks["cached_content_create"].call_args.kwargs
        assert ckwargs["model"] == "gemini-2.5-flash"
        assert ckwargs["system_instruction"] == long_system
        assert ckwargs["ttl"] == "5m"

        # from_cached_content used (NOT the keyword form on GenerativeModel).
        mocks["from_cached_content"].assert_called_once()
        fkwargs = mocks["from_cached_content"].call_args.kwargs
        assert fkwargs["cached_content"] is mocks["cached_obj"]
        # CRITICAL: system_instruction MUST NOT be passed here (already baked in).
        assert "system_instruction" not in fkwargs

        # Uncached GenerativeModel(...) constructor MUST NOT have been called.
        mocks["GenerativeModel"].assert_not_called()

        # Entry stored.
        GeminiProvider = _live_module().GeminiProvider
        assert len(GeminiProvider._context_cache_index) == 1
        entry = next(iter(GeminiProvider._context_cache_index.values()))
        assert entry.cache_name == "cachedContents/abc123"
        assert entry.cached_obj is mocks["cached_obj"]
        assert entry.model == "gemini-2.5-flash"


class TestContextCacheReusedOnSecondCall:
    def test_context_cache_reused_on_second_call_within_ttl(self):
        genai, mocks = _make_fake_genai()
        provider = _new_provider(genai)
        long_system = _long_system()

        # 1st call — populates cache.
        _run(
            provider.agenerate(
                system=long_system,
                messages=[{"role": "user", "content": "hi"}],
                model="gemini-2.5-flash",
                max_tokens=4096,
                temperature=0.0,
            )
        )

        # 2nd call — same (model, system) → must reuse.
        _run(
            provider.agenerate(
                system=long_system,
                messages=[{"role": "user", "content": "hi again"}],
                model="gemini-2.5-flash",
                max_tokens=4096,
                temperature=0.0,
            )
        )

        # CachedContent.create called exactly ONCE (not twice).
        assert mocks["cached_content_create"].call_count == 1, (
            "2nd call within TTL should reuse the existing CachedContent, "
            f"got {mocks['cached_content_create'].call_count} create calls"
        )

        # FU16 P2-5: ``GenerativeModel.from_cached_content`` is now ALSO
        # cached via ``_generative_model_cache_index``. The 1st call
        # constructs once via from_cached_content; the 2nd call hits the
        # model cache and reuses the same constructed model_obj — so
        # ``from_cached_content.call_count == 1``, not 2 as in the pre-FU16
        # contract. This is by-design: avoiding redundant Python-side
        # ``GenerativeModel.from_cached_content`` calls is the WHOLE point
        # of FU16. The server-side reuse contract is still verified by
        # ``cached_content_create.call_count == 1`` above.
        assert mocks["from_cached_content"].call_count == 1, (
            "post-FU16: 2nd call should hit the GenerativeModel cache and "
            "reuse the constructed model_obj; got "
            f"{mocks['from_cached_content'].call_count}"
        )

        # The single from_cached_content call passed cached_obj.
        for call in mocks["from_cached_content"].call_args_list:
            assert call.kwargs["cached_content"] is mocks["cached_obj"]


class TestContextCacheRefreshedAfterTTL:
    def test_context_cache_refreshed_after_ttl_expiry(self):
        genai, mocks = _make_fake_genai()
        provider = _new_provider(genai)
        long_system = _long_system()

        # 1st call.
        _run(
            provider.agenerate(
                system=long_system,
                messages=[{"role": "user", "content": "hi"}],
                model="gemini-2.5-flash",
                max_tokens=4096,
                temperature=0.0,
            )
        )

        # Manipulate last_used to be well outside the reuse window.
        # Reuse window is _GEMINI_CACHE_TTL_SECONDS - margin = 270s.
        GeminiProvider = _live_module().GeminiProvider
        assert len(GeminiProvider._context_cache_index) == 1
        entry = next(iter(GeminiProvider._context_cache_index.values()))
        entry.last_used = entry.last_used - 600  # 10 min ago

        # 2nd call — same key but expired → must re-create.
        _run(
            provider.agenerate(
                system=long_system,
                messages=[{"role": "user", "content": "hi again"}],
                model="gemini-2.5-flash",
                max_tokens=4096,
                temperature=0.0,
            )
        )

        assert mocks["cached_content_create"].call_count == 2, (
            "expired cache entry should trigger re-create, "
            f"got {mocks['cached_content_create'].call_count}"
        )


# ---------------------------------------------------------------------------
# Skip paths
# ---------------------------------------------------------------------------


class TestContextCacheSkippedForShortSystem:
    def test_context_cache_skipped_for_short_system(self):
        genai, mocks = _make_fake_genai()
        provider = _new_provider(genai)
        # Well under the per-model threshold (4096 for 2.5-flash, looked up
        # via GeminiProvider._gemini_cache_min_chars).
        short_system = "You are an OCSF Lua generator."

        _run(
            provider.agenerate(
                system=short_system,
                messages=[{"role": "user", "content": "hi"}],
                model="gemini-2.5-flash",
                max_tokens=4096,
                temperature=0.0,
                cache_breakpoints=True,
            )
        )

        mocks["cached_content_create"].assert_not_called()
        mocks["from_cached_content"].assert_not_called()
        # Uncached path used.
        mocks["GenerativeModel"].assert_called_once()
        ukwargs = mocks["GenerativeModel"].call_args.kwargs
        assert ukwargs["system_instruction"] == short_system
        assert ukwargs["model_name"] == "gemini-2.5-flash"


class TestContextCacheSkippedWhenBreakpointsDisabled:
    def test_context_cache_skipped_when_breakpoints_disabled(self):
        genai, mocks = _make_fake_genai()
        provider = _new_provider(genai)
        long_system = _long_system()

        _run(
            provider.agenerate(
                system=long_system,
                messages=[{"role": "user", "content": "hi"}],
                model="gemini-2.5-flash",
                max_tokens=4096,
                temperature=0.0,
                cache_breakpoints=False,
            )
        )

        mocks["cached_content_create"].assert_not_called()
        mocks["from_cached_content"].assert_not_called()
        mocks["GenerativeModel"].assert_called_once()


# ---------------------------------------------------------------------------
# usage_metadata.cached_content_token_count surfaced
# ---------------------------------------------------------------------------


class TestCachedContentTokenCountSurfaced:
    def test_cached_content_token_count_surfaced_to_response(self):
        genai, mocks = _make_fake_genai(cached_content_token_count=42)
        provider = _new_provider(genai)
        long_system = _long_system()

        resp = _run(
            provider.agenerate(
                system=long_system,
                messages=[{"role": "user", "content": "hi"}],
                model="gemini-2.5-flash",
                max_tokens=4096,
                temperature=0.0,
            )
        )

        assert resp.cache_read_input_tokens == 42, (
            "usage_metadata.cached_content_token_count must surface to "
            f"LLMResponse.cache_read_input_tokens; got {resp.cache_read_input_tokens}"
        )
        assert resp.provider == "gemini"
        assert resp.model == "gemini-2.5-flash"


# ---------------------------------------------------------------------------
# Failure resilience — never block the call
# ---------------------------------------------------------------------------


class TestCacheCreateFailureFallsBack:
    def test_cache_create_failure_falls_back_to_uncached(self, caplog):
        genai, mocks = _make_fake_genai(
            cache_create_raises=RuntimeError("cache server unavailable"),
        )
        provider = _new_provider(genai)
        long_system = _long_system()

        with caplog.at_level("WARNING", logger="components.llm_provider"):
            resp = _run(
                provider.agenerate(
                    system=long_system,
                    messages=[{"role": "user", "content": "hi"}],
                    model="gemini-2.5-flash",
                    max_tokens=4096,
                    temperature=0.0,
                )
            )

        # WARNING logged.
        assert any(
            "context cache create failed" in r.getMessage().lower()
            for r in caplog.records
        ), f"expected WARNING, got records: {[r.getMessage() for r in caplog.records]}"

        # Uncached fallback used.
        mocks["GenerativeModel"].assert_called_once()
        mocks["from_cached_content"].assert_not_called()

        # Call still succeeds.
        assert resp.text == "ok"
        assert resp.provider == "gemini"


class TestFromCachedContentFailureFallsBack:
    def test_from_cached_content_failure_falls_back_to_uncached(self, caplog):
        genai, mocks = _make_fake_genai(
            from_cached_raises=RuntimeError("cached_content not found"),
        )
        provider = _new_provider(genai)
        long_system = _long_system()

        with caplog.at_level("WARNING", logger="components.llm_provider"):
            resp = _run(
                provider.agenerate(
                    system=long_system,
                    messages=[{"role": "user", "content": "hi"}],
                    model="gemini-2.5-flash",
                    max_tokens=4096,
                    temperature=0.0,
                )
            )

        # CachedContent.create succeeded; from_cached_content failed.
        mocks["cached_content_create"].assert_called_once()
        mocks["from_cached_content"].assert_called_once()

        # WARNING logged.
        assert any(
            "from_cached_content failed" in r.getMessage().lower()
            for r in caplog.records
        ), f"expected WARNING, got records: {[r.getMessage() for r in caplog.records]}"

        # Uncached fallback constructor used.
        mocks["GenerativeModel"].assert_called_once()

        # Call still succeeds.
        assert resp.text == "ok"
        assert resp.provider == "gemini"


# ---------------------------------------------------------------------------
# DA-FU15 round 3 Fix 1 — concurrent-create race serialization (asyncio.Lock)
# ---------------------------------------------------------------------------


class TestConcurrentFirstCallsSerializeCreate:
    """Without the lock, N concurrent first-calls on the same (model, system)
    all see ``dict.get(key) is None``, all fire ``CachedContent.create`` in
    parallel, and leak N-1 billable server-side caches (each lives until
    Google evicts at TTL). The lock + double-checked-locking pattern in
    ``_maybe_get_or_create_cache`` serializes the slow path so exactly ONE
    coroutine creates per cold (model, system); the others wait, re-check
    the dict after acquiring the lock, and reuse the winner's entry.
    """

    def test_concurrent_first_calls_serialize_to_single_create(self):
        # Slow down CachedContent.create so all 5 coroutines genuinely
        # overlap inside the slow path. Without the artificial delay the
        # event loop could schedule them serially and pass even without
        # the lock.
        import threading
        gate = threading.Event()
        original_create_running = threading.Event()

        genai, mocks = _make_fake_genai()
        cached_obj = mocks["cached_obj"]

        def slow_create(*args, **kwargs):
            original_create_running.set()
            # Hold here until the test releases the gate. This guarantees
            # all 5 coroutines have observed dict.get(key) is None AND
            # piled up at the lock before any of them complete the create.
            gate.wait(timeout=5.0)
            return cached_obj

        mocks["cached_content_create"].side_effect = slow_create

        provider = _new_provider(genai)
        long_system = _long_system()

        async def one_call():
            return await provider.agenerate(
                system=long_system,
                messages=[{"role": "user", "content": "go"}],
                model="gemini-2.5-flash",
                max_tokens=64,
                temperature=0.0,
                cache_breakpoints=True,
            )

        async def driver():
            # Schedule 5 coroutines, then release the gate so the (single)
            # winner's create can complete.
            tasks = [asyncio.create_task(one_call()) for _ in range(5)]
            # Yield until the first create has actually entered the SDK.
            await asyncio.sleep(0.05)
            assert original_create_running.is_set(), (
                "expected the winner's CachedContent.create to be in-flight"
            )
            gate.set()
            return await asyncio.gather(*tasks)

        results = _run(driver())

        assert len(results) == 5, f"expected 5 results, got {len(results)}"
        # The contract: 5 concurrent calls on the SAME (model, system) must
        # produce EXACTLY 1 wire create. >1 means the lock didn't serialize
        # and we leaked server-side cache resources.
        assert mocks["cached_content_create"].call_count == 1, (
            "concurrent first-calls leaked extra CachedContent.create wire "
            "calls: got "
            f"{mocks['cached_content_create'].call_count}, expected 1"
        )
        # FU16 P2-5: post-FU16 the GenerativeModel cache also serializes
        # ``from_cached_content`` calls — once the winner constructs the
        # model_obj, the 4 hit-after-lock siblings re-check the model cache
        # under the (now shared) ``_cache_lock`` and reuse the same model
        # object. So ``from_cached_content`` runs exactly ONCE total, not 5.
        # The pre-FU16 contract was "5 calls (1 winner + 4 hit-after-cache-
        # lock)"; FU16 supersedes that with "1 call total".
        assert mocks["from_cached_content"].call_count == 1, (
            "post-FU16: from_cached_content should run exactly ONCE for "
            "5 concurrent first-calls on the same model_cache_key; got "
            f"{mocks['from_cached_content'].call_count}"
        )

        # And the dict has exactly 1 entry.
        GeminiProvider = _live_module().GeminiProvider
        assert len(GeminiProvider._context_cache_index) == 1


# ---------------------------------------------------------------------------
# DA-FU15 round 3 Fix 2 — TTL constant drives SDK string + settings overrides
# ---------------------------------------------------------------------------


class TestTTLConstantDrivesSDKString:
    """The SDK ``ttl=`` string must be derived from the seconds constant via
    ``_seconds_to_gemini_ttl``, not hardcoded. Otherwise changing the
    constant in one place silently leaves the wire stale.
    """

    def test_seconds_to_gemini_ttl_unit_conversions(self):
        mod = _live_module()
        assert mod._seconds_to_gemini_ttl(300) == "5m"
        assert mod._seconds_to_gemini_ttl(600) == "10m"
        assert mod._seconds_to_gemini_ttl(3600) == "1h"
        assert mod._seconds_to_gemini_ttl(7200) == "2h"
        # Non-clean multiples fall through to seconds form.
        assert mod._seconds_to_gemini_ttl(301) == "301s"
        # Non-positive defends with a 1s floor.
        assert mod._seconds_to_gemini_ttl(0) == "1s"
        assert mod._seconds_to_gemini_ttl(-5) == "1s"

    def test_ttl_constant_drives_sdk_ttl_string(self, monkeypatch):
        """Bumping ``_GEMINI_CACHE_TTL_SECONDS`` propagates to the wire."""
        mod = _live_module()
        monkeypatch.setattr(mod, "_GEMINI_CACHE_TTL_SECONDS", 600)

        genai, mocks = _make_fake_genai()
        provider = _new_provider(genai)
        long_system = _long_system()

        _run(
            provider.agenerate(
                system=long_system,
                messages=[{"role": "user", "content": "hi"}],
                model="gemini-2.5-flash",
                max_tokens=4096,
                temperature=0.0,
                cache_breakpoints=True,
            )
        )

        ckwargs = mocks["cached_content_create"].call_args.kwargs
        assert ckwargs["ttl"] == "10m", (
            "TTL constant 600s must produce SDK string '10m'; "
            f"got {ckwargs['ttl']!r}"
        )

    def test_ttl_settings_override_takes_precedence(self, monkeypatch):
        """``providers.gemini.cache_ttl_seconds`` setting overrides the
        constant — operator can extend TTL without a code change."""
        mod = _live_module()

        def fake_settings_get(path):
            if path == "providers.gemini.cache_ttl_seconds":
                return 1200
            return None

        monkeypatch.setattr(mod, "_settings_get", fake_settings_get)

        genai, mocks = _make_fake_genai()
        provider = _new_provider(genai)
        long_system = _long_system()

        _run(
            provider.agenerate(
                system=long_system,
                messages=[{"role": "user", "content": "hi"}],
                model="gemini-2.5-flash",
                max_tokens=4096,
                temperature=0.0,
                cache_breakpoints=True,
            )
        )

        ckwargs = mocks["cached_content_create"].call_args.kwargs
        assert ckwargs["ttl"] == "20m", (
            "settings override 1200s must produce SDK string '20m'; "
            f"got {ckwargs['ttl']!r}"
        )


# ---------------------------------------------------------------------------
# DA-FU15 round 3 Fix 3 — invalidate dead dict entry on from_cached_content 404
# ---------------------------------------------------------------------------


class TestFromCachedContent404InvalidatesEntry:
    """When ``from_cached_content`` raises (cache evicted server-side), the
    handler must remove the dead entry from ``_context_cache_index`` so the
    next call re-creates rather than retrying the same bad ``cached_obj``
    handle and 404-ing again.
    """

    def test_from_cached_content_404_invalidates_dict_entry(self, caplog):
        # First call — populate cache (no failure).
        genai, mocks = _make_fake_genai()
        provider = _new_provider(genai)
        long_system = _long_system()

        _run(
            provider.agenerate(
                system=long_system,
                messages=[{"role": "user", "content": "hi"}],
                model="gemini-2.5-flash",
                max_tokens=4096,
                temperature=0.0,
            )
        )

        GeminiProvider = _live_module().GeminiProvider
        assert len(GeminiProvider._context_cache_index) == 1, (
            "first call should populate cache"
        )
        key_before = next(iter(GeminiProvider._context_cache_index.keys()))

        # Now flip from_cached_content to raise (simulating 404 because the
        # server-side cache was evicted between calls).
        mocks["from_cached_content"].side_effect = RuntimeError(
            "cached_content not found (404)"
        )

        # FU16 P2-5: clear the GenerativeModel cache between calls so the
        # 2nd call actually re-invokes ``from_cached_content`` (which is what
        # exercises the 404 path under test). Without this clear, the 1st
        # call's successfully-constructed model_obj would be reused from
        # ``_generative_model_cache_index`` and ``from_cached_content`` would
        # never be re-called — the invalidation contract under test would
        # be unreachable. In production this happens naturally when the
        # local model cache entry gets evicted (settings mtime change) or
        # the server-side cache TTL has expired, making the next call enter
        # the slow path. The test simulates that here.
        GeminiProvider._generative_model_cache_index.clear()

        # Second call — should detect the dead entry, invalidate it, and
        # fall through to the uncached path.
        with caplog.at_level("WARNING", logger="components.llm_provider"):
            resp = _run(
                provider.agenerate(
                    system=long_system,
                    messages=[{"role": "user", "content": "hi again"}],
                    model="gemini-2.5-flash",
                    max_tokens=4096,
                    temperature=0.0,
                )
            )

        # WARNING mentions invalidation.
        assert any(
            "invalidating local entry" in r.getMessage().lower()
            for r in caplog.records
        ), (
            "expected WARNING mentioning invalidation; got: "
            f"{[r.getMessage() for r in caplog.records]}"
        )

        # Dict entry GONE (this is the actual contract being verified).
        assert key_before not in GeminiProvider._context_cache_index, (
            "dead entry should have been removed from "
            "_context_cache_index after from_cached_content raised; "
            f"still present: {list(GeminiProvider._context_cache_index.keys())}"
        )

        # Uncached fallback used and call still succeeds.
        mocks["GenerativeModel"].assert_called_once()
        assert resp.text == "ok"
        assert resp.provider == "gemini"


# ---------------------------------------------------------------------------
# DA-FU15 follow-up #1 — per-model cache eligibility threshold
# ---------------------------------------------------------------------------


class TestPerModelCacheMinChars:
    """Per Google AI Forum (May 2026): 2.5-flash min is 1024 tokens
    (~4096 chars), 2.5-pro min is 2048 tokens (~8192 chars). Mirrors the
    FU14 Anthropic-Haiku threshold-bump pattern: under-specifying the
    threshold reliably fails ``CachedContent.create`` with an API minimum
    error and produces zero cache benefit. Unknown / older models default
    to the largest known minimum (8192) so we never under-spec.
    """

    def test_min_chars_for_gemini_25_pro_returns_8192(self):
        GeminiProvider = _live_module().GeminiProvider
        assert (
            GeminiProvider._gemini_cache_min_chars("gemini-2.5-pro") == 8192
        )
        # Suffix variants match.
        assert (
            GeminiProvider._gemini_cache_min_chars("gemini-2.5-pro-002")
            == 8192
        )

    def test_min_chars_for_gemini_25_flash_returns_4096(self):
        GeminiProvider = _live_module().GeminiProvider
        assert (
            GeminiProvider._gemini_cache_min_chars("gemini-2.5-flash") == 4096
        )
        assert (
            GeminiProvider._gemini_cache_min_chars("gemini-2.5-flash-002")
            == 4096
        )

    def test_min_chars_for_unknown_gemini_returns_default_8192(self):
        GeminiProvider = _live_module().GeminiProvider
        # Older 1.5 / unknown models fall through to the conservative
        # largest-known default (8192).
        assert (
            GeminiProvider._gemini_cache_min_chars("gemini-1.5-pro") == 8192
        )
        assert GeminiProvider._gemini_cache_min_chars("") == 8192
        assert (
            GeminiProvider._gemini_cache_min_chars("some-unknown-model")
            == 8192
        )

    def test_pro_threshold_skips_caching_for_4096_char_system(self):
        """End-to-end: a 4096-char system clears 2.5-flash but NOT 2.5-pro.

        Without the per-model threshold, a 4096-7000-char system on
        2.5-pro would unconditionally trigger CachedContent.create and
        eat a WARNING + uncached fallback per call. With the per-model
        threshold, we skip the create round trip entirely.
        """
        genai, mocks = _make_fake_genai()
        provider = _new_provider(genai)
        # 5000 chars: above 2.5-flash min (4096), below 2.5-pro min (8192).
        mid_length_system = _long_system(min_chars=5000)
        assert 4096 <= len(mid_length_system) < 8192

        _run(
            provider.agenerate(
                system=mid_length_system,
                messages=[{"role": "user", "content": "hi"}],
                model="gemini-2.5-pro",
                max_tokens=4096,
                temperature=0.0,
                cache_breakpoints=True,
            )
        )

        # 2.5-pro: skipped because 5000 < 8192.
        mocks["cached_content_create"].assert_not_called()
        mocks["from_cached_content"].assert_not_called()
        mocks["GenerativeModel"].assert_called_once()

    def test_pro_threshold_engages_caching_above_8192_chars(self):
        """A long-enough system DOES engage caching on 2.5-pro."""
        genai, mocks = _make_fake_genai()
        provider = _new_provider(genai)
        long_pro_system = _long_system(min_chars=8500)
        assert len(long_pro_system) >= 8192

        _run(
            provider.agenerate(
                system=long_pro_system,
                messages=[{"role": "user", "content": "hi"}],
                model="gemini-2.5-pro",
                max_tokens=4096,
                temperature=0.0,
                cache_breakpoints=True,
            )
        )

        mocks["cached_content_create"].assert_called_once()
        mocks["from_cached_content"].assert_called_once()
        mocks["GenerativeModel"].assert_not_called()


# ---------------------------------------------------------------------------
# DA-FU15 follow-up #2 — asyncio.to_thread wrapping for blocking SDK calls
# ---------------------------------------------------------------------------


class TestCachingCallsRunInThreadPool:
    """Both ``genai.caching.CachedContent.create`` and
    ``genai.GenerativeModel.from_cached_content`` are SYNCHRONOUS SDK calls.
    They must be wrapped in ``asyncio.to_thread`` inside ``_agenerate_once``
    so the gunicorn event loop isn't blocked under concurrent conversion
    load (the worker fans out conversions in async loops; a blocking
    create-cache stalls every other in-flight call).

    The existing ``model_obj.generate_content`` is already wrapped — this
    test verifies the new caching paths got the same treatment.
    """

    def test_caching_calls_run_in_thread_pool(self):
        mod = _live_module()
        genai, mocks = _make_fake_genai()
        provider = _new_provider(genai)
        long_system = _long_system()

        original_to_thread = mod.asyncio.to_thread
        seen_targets = []

        async def spy_to_thread(func, *args, **kwargs):
            seen_targets.append(func)
            return await original_to_thread(func, *args, **kwargs)

        # Patch the module-level ``asyncio`` symbol used inside _agenerate_once.
        try:
            mod.asyncio.to_thread = spy_to_thread  # type: ignore[assignment]
            _run(
                provider.agenerate(
                    system=long_system,
                    messages=[{"role": "user", "content": "hi"}],
                    model="gemini-2.5-flash",
                    max_tokens=4096,
                    temperature=0.0,
                    cache_breakpoints=True,
                )
            )
        finally:
            mod.asyncio.to_thread = original_to_thread  # type: ignore[assignment]

        # Three blocking SDK calls should have been routed via to_thread:
        #   1. CachedContent.create
        #   2. GenerativeModel.from_cached_content
        #   3. model_obj.generate_content (already wrapped pre-FU15)
        assert mocks["cached_content_create"] in seen_targets, (
            "CachedContent.create must be invoked via asyncio.to_thread; "
            f"saw targets: {[getattr(t, '__name__', repr(t)) for t in seen_targets]}"
        )
        assert mocks["from_cached_content"] in seen_targets, (
            "GenerativeModel.from_cached_content must be invoked via "
            "asyncio.to_thread; saw targets: "
            f"{[getattr(t, '__name__', repr(t)) for t in seen_targets]}"
        )
        # And generate_content (sanity — pre-existing behaviour).
        assert (
            mocks["cached_model_instance"].generate_content in seen_targets
        ), (
            "model_obj.generate_content must remain wrapped in to_thread; "
            f"saw targets: {[getattr(t, '__name__', repr(t)) for t in seen_targets]}"
        )


# ---------------------------------------------------------------------------
# DA-Architecture FU10 follow-up — typed signature
# ---------------------------------------------------------------------------


class TestTypedSignaturePresent:
    """``GeminiProvider.agenerate`` must expose the explicit typed signature,
    matching ``AnthropicProvider`` / ``OpenAIProvider``. The previous form
    was ``(self, *args, **kwargs)`` which broke Protocol static-analysis."""

    def test_typed_signature_present_on_agenerate(self):
        GeminiProvider = _live_module().GeminiProvider
        sig = inspect.signature(GeminiProvider.agenerate)
        params = sig.parameters

        expected = [
            "self",
            "system",
            "messages",
            "model",
            "max_tokens",
            "temperature",
            "cache_breakpoints",
            "messages_split",
            "previous_response_id",
            "response_format",
        ]
        assert list(params) == expected, (
            f"GeminiProvider.agenerate signature drift: "
            f"expected {expected}, got {list(params)}"
        )

        # No VAR_POSITIONAL / VAR_KEYWORD on the public method.
        for name, p in params.items():
            assert p.kind != inspect.Parameter.VAR_POSITIONAL, (
                f"{name} is VAR_POSITIONAL — typed signature regressed"
            )
            assert p.kind != inspect.Parameter.VAR_KEYWORD, (
                f"{name} is VAR_KEYWORD — typed signature regressed"
            )

    def test_typed_signature_defaults_match_protocol(self):
        # Defaults must match the Protocol surface in LLMProvider.
        GeminiProvider = _live_module().GeminiProvider
        AnthropicProvider = _live_module().AnthropicProvider

        gemini_sig = inspect.signature(GeminiProvider.agenerate)
        anthropic_sig = inspect.signature(AnthropicProvider.agenerate)

        for name in (
            "max_tokens",
            "temperature",
            "cache_breakpoints",
            "messages_split",
            "previous_response_id",
            "response_format",
        ):
            assert (
                gemini_sig.parameters[name].default
                == anthropic_sig.parameters[name].default
            ), (
                f"GeminiProvider.agenerate default for {name!r} differs "
                "from AnthropicProvider.agenerate"
            )


# ---------------------------------------------------------------------------
# Sanity — legacy uncached path still works
# ---------------------------------------------------------------------------


class TestExistingUncachedPathUnchanged:
    def test_existing_uncached_path_unchanged_when_no_caching(self):
        """When caching is not engaged (short system + cache_breakpoints=True),
        the legacy ``GenerativeModel(model_name=, system_instruction=, ...)``
        path remains the only thing called and the response shape is unchanged.
        """
        genai, mocks = _make_fake_genai()
        provider = _new_provider(genai)
        short_system = "short"

        resp = _run(
            provider.agenerate(
                system=short_system,
                messages=[{"role": "user", "content": "hi"}],
                model="gemini-2.5-flash",
                max_tokens=4096,
                temperature=0.0,
            )
        )

        mocks["cached_content_create"].assert_not_called()
        mocks["from_cached_content"].assert_not_called()
        mocks["GenerativeModel"].assert_called_once()

        # generate_content called with the messages list.
        mocks["uncached_model_instance"].generate_content.assert_called_once()
        call_args = (
            mocks["uncached_model_instance"].generate_content.call_args
        )
        sent = call_args.args[0]
        assert isinstance(sent, list) and len(sent) == 1
        assert sent[0]["role"] == "user"
        assert sent[0]["parts"] == [{"text": "hi"}]

        assert resp.text == "ok"
        assert resp.provider == "gemini"
        assert resp.model == "gemini-2.5-flash"
        assert resp.cache_read_input_tokens == 0
