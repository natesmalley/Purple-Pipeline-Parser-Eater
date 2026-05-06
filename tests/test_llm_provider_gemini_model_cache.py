"""FU16 P2-5 — GeminiProvider GenerativeModel reuse cache.

All MOCKED. No live API calls.

FU15 layered server-side ``CachedContent`` reuse via the
``_context_cache_index`` dict; FU16 layers a SEPARATE
``_generative_model_cache_index`` that caches the constructed
``GenerativeModel`` Python object so we don't pay the construction cost on
every agenerate call. Per the DA-FU15 round-3 forward-compat note, one
``CachedContent`` server-side resource can fan out to multiple
``GenerativeModel`` variants (different ``max_tokens`` / ``temperature`` /
``safety``) without re-creating the cache, so the two indices live
independently.

Cache key (documented 5-tuple):
    (model, max_tokens, temperature, safety_hash, cached_content_name_or_none)

Invalidation: SettingsStore mtime mismatch invalidates the entry — operator
settings changes take effect on the next call rather than being masked by a
stale cached model object. Concurrent first-calls serialize through
``_cache_lock`` (shared with the FU15 cache for TOCTOU safety) so we don't
construct N model objects in parallel for the same key.

Test-order safety: every test does a late-bound
``from components import llm_provider as mod`` (via ``_live_module()``) so a
re-import in a sibling test file (TestModuleImportIsLight in
``test_llm_provider.py``) doesn't strand our references on a stale module
object. See ``test_llm_provider_anthropic_thinking.py``'s ``_live_module()``
docstring for the full rationale.

Mocking strategy: tests inject a fake ``google.generativeai`` shape at
``provider._genai`` so ``_ensure_client()`` short-circuits without importing
the real SDK. We assert directly on the ``genai.GenerativeModel`` mock to
verify how many times the constructor was called.
"""
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers (mirror test_llm_provider_gemini_caching.py shape)
# ---------------------------------------------------------------------------


def _run(coro):
    return asyncio.run(coro)


def _live_module():
    """Return the CURRENT ``components.llm_provider`` module object.

    Late-bound for the same reason as the FU13/FU14/FU15 helpers — see the
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
    cached_content_token_count: int = 0,
    response_text: str = "ok",
):
    """Build a fake ``google.generativeai`` module with mocks we can assert on.

    Returns ``(genai, mocks)``. The constructor mock at ``mocks["GenerativeModel"]``
    is the focus of FU16 tests — we count its call_count.
    """
    genai = MagicMock(name="genai")

    cached_obj = MagicMock(name="cached_obj")
    cached_obj.name = "cachedContents/abc123"

    cached_content_create = MagicMock(name="CachedContent.create")
    cached_content_create.return_value = cached_obj
    genai.caching = MagicMock(name="caching")
    genai.caching.CachedContent = MagicMock(name="CachedContent")
    genai.caching.CachedContent.create = cached_content_create

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

    generative_model = MagicMock(
        name="GenerativeModel",
        return_value=uncached_model_instance,
    )
    generative_model.from_cached_content = MagicMock(
        return_value=cached_model_instance,
    )

    genai.GenerativeModel = generative_model
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

    Clears BOTH class-level cache indices first so prior tests can't bleed in.
    """
    GeminiProvider = _live_module().GeminiProvider
    GeminiProvider._context_cache_index.clear()
    GeminiProvider._generative_model_cache_index.clear()
    provider = GeminiProvider(api_key="test-key")
    provider._genai = genai_mock
    return provider


# ---------------------------------------------------------------------------
# Cache key — same params reuse, different params miss
# ---------------------------------------------------------------------------


class TestGenerativeModelReusedForSameParams:
    """Identical (model, max_tokens, temperature, system, safety) → exactly
    ONE construction across two agenerate calls. The whole point of FU16."""

    def test_generative_model_reused_for_same_params(self):
        genai, mocks = _make_fake_genai()
        provider = _new_provider(genai)
        short_system = "short system below cache threshold"

        for _ in range(2):
            _run(
                provider.agenerate(
                    system=short_system,
                    messages=[{"role": "user", "content": "hi"}],
                    model="gemini-2.5-flash",
                    max_tokens=4096,
                    temperature=0.0,
                    cache_breakpoints=False,
                )
            )

        assert mocks["GenerativeModel"].call_count == 1, (
            "identical params across 2 calls must construct exactly ONCE; "
            f"got {mocks['GenerativeModel'].call_count}"
        )


class TestGenerativeModelRecreatedForDifferentTemperature:
    def test_generative_model_recreated_for_different_temperature(self):
        genai, mocks = _make_fake_genai()
        provider = _new_provider(genai)
        short_system = "short system"

        _run(
            provider.agenerate(
                system=short_system,
                messages=[{"role": "user", "content": "hi"}],
                model="gemini-2.5-flash",
                max_tokens=4096,
                temperature=0.0,
                cache_breakpoints=False,
            )
        )
        _run(
            provider.agenerate(
                system=short_system,
                messages=[{"role": "user", "content": "hi"}],
                model="gemini-2.5-flash",
                max_tokens=4096,
                temperature=0.7,
                cache_breakpoints=False,
            )
        )

        assert mocks["GenerativeModel"].call_count == 2, (
            "different temperature → different cache key → 2 constructions; "
            f"got {mocks['GenerativeModel'].call_count}"
        )


class TestGenerativeModelRecreatedForDifferentMaxTokens:
    def test_generative_model_recreated_for_different_max_tokens(self):
        genai, mocks = _make_fake_genai()
        provider = _new_provider(genai)
        short_system = "short system"

        _run(
            provider.agenerate(
                system=short_system,
                messages=[{"role": "user", "content": "hi"}],
                model="gemini-2.5-flash",
                max_tokens=4096,
                temperature=0.0,
                cache_breakpoints=False,
            )
        )
        _run(
            provider.agenerate(
                system=short_system,
                messages=[{"role": "user", "content": "hi"}],
                model="gemini-2.5-flash",
                max_tokens=8192,
                temperature=0.0,
                cache_breakpoints=False,
            )
        )

        assert mocks["GenerativeModel"].call_count == 2, (
            "different max_tokens → different cache key → 2 constructions; "
            f"got {mocks['GenerativeModel'].call_count}"
        )


class TestGenerativeModelRecreatedForDifferentSafety:
    """Different safety settings → different ``safety_hash`` → different
    cache key → constructor called twice. Verifies the safety_hash component
    of the documented 5-tuple actually participates in the key."""

    def test_generative_model_recreated_for_different_safety(self):
        genai, mocks = _make_fake_genai()
        provider = _new_provider(genai)
        short_system = "short system"

        # First call uses the default safety list.
        _run(
            provider.agenerate(
                system=short_system,
                messages=[{"role": "user", "content": "hi"}],
                model="gemini-2.5-flash",
                max_tokens=4096,
                temperature=0.0,
                cache_breakpoints=False,
            )
        )
        # Patch _agenerate_once via a wrapper — we can't pass safety from the
        # outside, so we instead poke the safety_hash by patching the helper.
        # Simpler: directly exercise the cache_key helper to prove safety
        # participation, then exercise via differing safety lists below.
        GeminiProvider = _live_module().GeminiProvider

        key_default = GeminiProvider._generative_model_cache_key(
            "gemini-2.5-flash", 4096, 0.0,
            [{"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"}],
            None,
        )
        key_strict = GeminiProvider._generative_model_cache_key(
            "gemini-2.5-flash", 4096, 0.0,
            [{"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_LOW_AND_ABOVE"}],
            None,
        )
        assert key_default != key_strict, (
            "different safety settings must produce different cache keys; "
            f"both produced {key_default}"
        )

        # End-to-end: monkeypatch the safety list constructed inside
        # _agenerate_once so we can prove the runtime path picks up safety
        # changes too. We replace the GeminiProvider's _safety_hash to
        # return a counter that flips between calls — same effect as
        # different safety lists hitting different hashes.
        call_count = {"n": 0}

        def alternating_safety_hash(safety_settings):
            call_count["n"] += 1
            return f"safety-hash-variant-{call_count['n']}"

        # Capture the original via __dict__ so we get the underlying
        # staticmethod descriptor, not the unwrapped function. Restoring with
        # a plain function would convert it back to a regular method (because
        # bare-function class attrs become bound methods on instance access)
        # and break every subsequent call site that does ``self._safety_hash(x)``.
        original = GeminiProvider.__dict__["_safety_hash"]
        try:
            GeminiProvider._safety_hash = staticmethod(alternating_safety_hash)
            # Reset mocks since first call already happened above with the
            # real safety_hash.
            mocks["GenerativeModel"].reset_mock()
            GeminiProvider._generative_model_cache_index.clear()

            _run(
                provider.agenerate(
                    system=short_system,
                    messages=[{"role": "user", "content": "hi"}],
                    model="gemini-2.5-flash",
                    max_tokens=4096,
                    temperature=0.0,
                    cache_breakpoints=False,
                )
            )
            _run(
                provider.agenerate(
                    system=short_system,
                    messages=[{"role": "user", "content": "hi"}],
                    model="gemini-2.5-flash",
                    max_tokens=4096,
                    temperature=0.0,
                    cache_breakpoints=False,
                )
            )

            assert mocks["GenerativeModel"].call_count == 2, (
                "alternating safety_hash → distinct cache keys → 2 "
                f"constructions; got {mocks['GenerativeModel'].call_count}"
            )
        finally:
            GeminiProvider._safety_hash = original  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Settings mtime invalidation
# ---------------------------------------------------------------------------


class TestGenerativeModelInvalidatedOnSettingsMtimeChange:
    """An operator settings change (manifested as a SettingsStore mtime bump)
    must invalidate the cached model entry. Otherwise switching providers /
    models / API keys via the Settings tab would be silently masked by a
    stale model object."""

    def test_generative_model_invalidated_on_settings_mtime_change(
        self, monkeypatch,
    ):
        mod = _live_module()
        genai, mocks = _make_fake_genai()
        provider = _new_provider(genai)
        short_system = "short system"

        # First call: settings mtime = 1000.0
        mtime_state = {"current": 1000.0}

        def fake_mtime():
            return mtime_state["current"]

        monkeypatch.setattr(mod, "_settings_mtime", fake_mtime)

        _run(
            provider.agenerate(
                system=short_system,
                messages=[{"role": "user", "content": "hi"}],
                model="gemini-2.5-flash",
                max_tokens=4096,
                temperature=0.0,
                cache_breakpoints=False,
            )
        )
        assert mocks["GenerativeModel"].call_count == 1

        # Bump mtime — operator changed settings. Next call must re-construct.
        mtime_state["current"] = 2000.0

        _run(
            provider.agenerate(
                system=short_system,
                messages=[{"role": "user", "content": "hi"}],
                model="gemini-2.5-flash",
                max_tokens=4096,
                temperature=0.0,
                cache_breakpoints=False,
            )
        )
        assert mocks["GenerativeModel"].call_count == 2, (
            "settings mtime change must invalidate cached model entry; "
            f"got {mocks['GenerativeModel'].call_count} constructions, "
            "expected 2 (cache + re-cache after mtime bump)"
        )


# ---------------------------------------------------------------------------
# cached_content_name participates in the cache key
# ---------------------------------------------------------------------------


class TestCacheKeyIncludesCachedContentName:
    """A cached vs uncached call for otherwise-identical params must produce
    DIFFERENT cache entries. The 5th component of the key
    (cached_content_name_or_none) makes the from_cached_content variant and
    the plain GenerativeModel variant non-colliding."""

    def test_cache_key_includes_cached_content_name(self):
        genai, mocks = _make_fake_genai()
        provider = _new_provider(genai)

        # First call: long system → caching engages → from_cached_content used.
        long_system = (
            "You are an OCSF Lua expert. Apply patterns A-E. Inline helpers. "
            * 200  # well above 4096-char threshold
        )
        assert len(long_system) > 5000

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

        # Second call: short system → no caching → plain GenerativeModel used.
        short_system = "short"
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

        # Constructor called for the uncached variant; from_cached_content
        # called for the cached variant. They are independent cache entries
        # so the second call's GenerativeModel construction is NOT skipped
        # by the first call's from_cached_content cache hit.
        assert mocks["from_cached_content"].call_count == 1, (
            "expected 1 from_cached_content call (1st agenerate, cached); "
            f"got {mocks['from_cached_content'].call_count}"
        )
        assert mocks["GenerativeModel"].call_count == 1, (
            "expected 1 GenerativeModel(...) call (2nd agenerate, uncached); "
            f"got {mocks['GenerativeModel'].call_count}"
        )

        # And the cache index has 2 entries with different 5th-tuple components.
        GeminiProvider = _live_module().GeminiProvider
        keys = list(GeminiProvider._generative_model_cache_index.keys())
        assert len(keys) == 2, (
            f"expected 2 distinct cache entries (cached + uncached); got {keys}"
        )
        cached_content_names = {k[4] for k in keys}
        assert cached_content_names == {None, "cachedContents/abc123"}, (
            "5th tuple component must distinguish cached vs uncached entries; "
            f"got {cached_content_names}"
        )


# ---------------------------------------------------------------------------
# Concurrent first-calls serialize through the shared _cache_lock
# ---------------------------------------------------------------------------


class TestConcurrentFirstCallsSerializeToSingleConstruction:
    """5 concurrent first-calls on the same cache key must construct EXACTLY
    1 ``GenerativeModel`` object — the same ``_cache_lock`` from FU15 also
    protects the model-cache index for TOCTOU safety. Without the lock, all
    5 would observe ``dict.get(key) is None`` and construct in parallel.
    """

    def test_concurrent_first_calls_serialize_to_single_construction(self):
        import threading

        gate = threading.Event()
        first_construction_running = threading.Event()

        genai, mocks = _make_fake_genai()

        def slow_constructor(*args, **kwargs):
            first_construction_running.set()
            gate.wait(timeout=5.0)
            return mocks["uncached_model_instance"]

        # Replace the constructor side_effect with a gated slow path.
        mocks["GenerativeModel"].side_effect = slow_constructor

        provider = _new_provider(genai)
        short_system = "short"

        async def one_call():
            return await provider.agenerate(
                system=short_system,
                messages=[{"role": "user", "content": "go"}],
                model="gemini-2.5-flash",
                max_tokens=64,
                temperature=0.0,
                cache_breakpoints=False,
            )

        async def driver():
            tasks = [asyncio.create_task(one_call()) for _ in range(5)]
            # Yield until the first constructor call has actually entered.
            await asyncio.sleep(0.05)
            assert first_construction_running.is_set(), (
                "expected the winner's constructor to be in-flight"
            )
            gate.set()
            return await asyncio.gather(*tasks)

        results = _run(driver())

        assert len(results) == 5, f"expected 5 results, got {len(results)}"
        assert mocks["GenerativeModel"].call_count == 1, (
            "concurrent first-calls leaked extra GenerativeModel "
            "constructions: got "
            f"{mocks['GenerativeModel'].call_count}, expected 1 "
            "(the _cache_lock should serialize cold-cache construction)"
        )

        GeminiProvider = _live_module().GeminiProvider
        assert len(GeminiProvider._generative_model_cache_index) == 1


# ---------------------------------------------------------------------------
# FU15 soft-item 2b — _max_output_tokens_for tuple-of-tuples conversion
# ---------------------------------------------------------------------------


class TestMaxOutputTokensForTupleOfTuplesShape:
    """FU15 introduced ``_GEMINI_CACHE_MIN_CHARS_BY_MODEL`` as a tuple-of-
    tuples; the sibling ``_max_output_tokens_for`` was still an if-chain.
    FU16 follow-up converts it to the same shape for class-internal
    consistency. Values must be preserved exactly.
    """

    def test_max_output_tokens_for_25_pro_returns_65536(self):
        GeminiProvider = _live_module().GeminiProvider
        assert (
            GeminiProvider._max_output_tokens_for("gemini-2.5-pro") == 65536
        )
        # Suffix variants match.
        assert (
            GeminiProvider._max_output_tokens_for("gemini-2.5-pro-002")
            == 65536
        )

    def test_max_output_tokens_for_25_flash_returns_16384(self):
        GeminiProvider = _live_module().GeminiProvider
        assert (
            GeminiProvider._max_output_tokens_for("gemini-2.5-flash")
            == 16384
        )
        assert (
            GeminiProvider._max_output_tokens_for("gemini-2.5-flash-002")
            == 16384
        )

    def test_max_output_tokens_for_unknown_returns_default_16000(self):
        GeminiProvider = _live_module().GeminiProvider
        assert (
            GeminiProvider._max_output_tokens_for("gemini-1.5-pro") == 16000
        )
        assert GeminiProvider._max_output_tokens_for("") == 16000
        assert (
            GeminiProvider._max_output_tokens_for("some-unknown-model")
            == 16000
        )

    def test_max_output_tokens_table_shape_is_tuple_of_tuples(self):
        """Lock the contract: ``_GEMINI_MAX_OUTPUT_TOKENS_BY_MODEL`` must
        match the ``_GEMINI_CACHE_MIN_CHARS_BY_MODEL`` shape so future
        edits stay consistent."""
        GeminiProvider = _live_module().GeminiProvider
        table = GeminiProvider._GEMINI_MAX_OUTPUT_TOKENS_BY_MODEL
        assert isinstance(table, tuple), (
            "_GEMINI_MAX_OUTPUT_TOKENS_BY_MODEL must be a tuple (immutable); "
            f"got {type(table)}"
        )
        for entry in table:
            assert isinstance(entry, tuple) and len(entry) == 2, (
                f"each entry must be a (prefix, ceiling) 2-tuple; got {entry}"
            )
            prefix, ceiling = entry
            assert isinstance(prefix, str)
            assert isinstance(ceiling, int)


# ---------------------------------------------------------------------------
# DA-FU16 review — 404 invalidation gap on cached model_obj.generate_content
# ---------------------------------------------------------------------------


def _long_system(min_chars: int = 5000) -> str:
    """Mirror of the FU15 helper — returns a system long enough to engage
    the per-model cache threshold (4096 chars for gemini-2.5-flash)."""
    base = (
        "You are an expert OCSF Lua transform generator. "
        "Apply patterns A-E. Inline OCSF helpers. "
    )
    n = (min_chars // len(base)) + 1
    out = base * n
    assert len(out) >= min_chars
    return out


class TestGenerateContent404InvalidatesBothCaches:
    """When Google evicts the server-side ``CachedContent`` BEFORE our local
    ``_context_cache_index`` reuse window expires, the cached ``model_obj``'s
    wire call 404s — but the FU15 round-3 Fix 3 invalidation handler at the
    ``from_cached_content`` site cannot catch this. Without the matching
    invalidation at the ``generate_content`` site, ``_retry_with_backoff``
    burns all retries against the same dead handle.

    Contract under test:
      1. A successfully-cached call populates BOTH FU15 + FU16 indices.
      2. Server flips ``model_obj.generate_content`` to raise a 404-shaped
         exception (simulating mid-window cache eviction).
      3. The ``_agenerate_once`` exception handler detects the 404 shape,
         invalidates BOTH caches, and re-raises as transient
         ``LLMProviderError``.
      4. The retry from ``_retry_with_backoff`` would re-construct fresh
         (verified by both indices being empty post-raise — the next call
         hits the cold path).
    """

    def test_generate_content_404_invalidates_both_caches_and_raises_transient(
        self,
    ):
        from components import llm_provider as mod
        genai, mocks = _make_fake_genai()
        provider = _new_provider(genai)
        sys_text = _long_system(min_chars=5000)

        # First call: success, both caches populated.
        _run(
            provider.agenerate(
                system=sys_text,
                messages=[{"role": "user", "content": "go"}],
                model="gemini-2.5-flash",
                max_tokens=64,
                temperature=0.0,
                cache_breakpoints=True,
            )
        )

        GeminiProvider = _live_module().GeminiProvider
        assert len(GeminiProvider._context_cache_index) == 1, (
            "first call should populate FU15 _context_cache_index"
        )
        assert len(GeminiProvider._generative_model_cache_index) == 1, (
            "first call should populate FU16 _generative_model_cache_index"
        )

        # Now flip the cached model_obj's generate_content to raise a
        # 404-shaped error (simulating server-side cache eviction).
        class _Mock404(Exception):
            status_code = 404

            def __str__(self):
                return "CachedContent not found"

        mocks["cached_model_instance"].generate_content.side_effect = (
            _Mock404()
        )

        # Second call should raise LLMProviderError (transient) AFTER
        # invalidating BOTH caches. We bypass _retry_with_backoff by calling
        # _agenerate_once directly so the test asserts the SINGLE-attempt
        # contract — _retry_with_backoff is the next layer up and adds its
        # own backoff/retry semantics that aren't part of this gap fix.
        with pytest.raises(mod.LLMProviderError) as exc_info:
            _run(
                provider._agenerate_once(
                    system=sys_text,
                    messages=[{"role": "user", "content": "go"}],
                    model="gemini-2.5-flash",
                    max_tokens=64,
                    temperature=0.0,
                    cache_breakpoints=True,
                )
            )

        # Re-raised as transient LLMProviderError so _retry_with_backoff
        # treats it as retriable. NOT LLMProviderPermanentError — that
        # would have aborted the retry loop and burned the call.
        assert "cache eviction 404" in str(exc_info.value).lower(), (
            "exception message should identify the cache-eviction path; "
            f"got: {exc_info.value}"
        )

        # Both caches MUST be invalidated. The whole point of the fix.
        assert len(GeminiProvider._context_cache_index) == 0, (
            "FU15 _context_cache_index should be invalidated on "
            "generate_content 404; "
            f"still present: {list(GeminiProvider._context_cache_index.keys())}"
        )
        assert len(GeminiProvider._generative_model_cache_index) == 0, (
            "FU16 _generative_model_cache_index should be invalidated on "
            "generate_content 404; still present: "
            f"{list(GeminiProvider._generative_model_cache_index.keys())}"
        )

    def test_generate_content_non_404_error_does_NOT_invalidate(self):
        """Negative case: a non-404 ``generate_content`` failure (e.g. quota,
        500) must NOT invalidate the caches — they're still valid; only the
        wire call failed transiently. Ensures the predicate doesn't false-
        positive and bust caches on every flake.
        """
        from components import llm_provider as mod
        genai, mocks = _make_fake_genai()
        provider = _new_provider(genai)
        sys_text = _long_system(min_chars=5000)

        _run(
            provider.agenerate(
                system=sys_text,
                messages=[{"role": "user", "content": "go"}],
                model="gemini-2.5-flash",
                max_tokens=64,
                temperature=0.0,
                cache_breakpoints=True,
            )
        )

        GeminiProvider = _live_module().GeminiProvider
        assert len(GeminiProvider._context_cache_index) == 1
        assert len(GeminiProvider._generative_model_cache_index) == 1

        # Flip generate_content to raise a non-404 transient (e.g. 500).
        class _Mock500(Exception):
            status_code = 500

            def __str__(self):
                return "internal server error"

        mocks["cached_model_instance"].generate_content.side_effect = (
            _Mock500()
        )

        with pytest.raises(mod.LLMProviderError):
            _run(
                provider._agenerate_once(
                    system=sys_text,
                    messages=[{"role": "user", "content": "go"}],
                    model="gemini-2.5-flash",
                    max_tokens=64,
                    temperature=0.0,
                    cache_breakpoints=True,
                )
            )

        # Caches still populated — the failure was transient, not eviction.
        assert len(GeminiProvider._context_cache_index) == 1, (
            "non-404 error should NOT invalidate the FU15 cache"
        )
        assert len(GeminiProvider._generative_model_cache_index) == 1, (
            "non-404 error should NOT invalidate the FU16 cache"
        )


class TestLooksLikeCacheEviction404Predicate:
    """Unit-level predicate tests so future regressions to
    ``_looks_like_cache_eviction_404`` are caught directly, not via the
    end-to-end test only."""

    def test_predicate_matches_message_with_cachedcontent(self):
        from components.llm_provider import _looks_like_cache_eviction_404
        assert _looks_like_cache_eviction_404(
            Exception("CachedContent not found"),
        )
        # Case-insensitive + whitespace-tolerant.
        assert _looks_like_cache_eviction_404(
            Exception("cachedcontent gone"),
        )
        assert _looks_like_cache_eviction_404(
            Exception("Cached Content evicted"),
        )

    def test_predicate_matches_status_code_404(self):
        from components.llm_provider import _looks_like_cache_eviction_404

        class _E(Exception):
            status_code = 404

        assert _looks_like_cache_eviction_404(_E("opaque"))

    def test_predicate_matches_code_404(self):
        from components.llm_provider import _looks_like_cache_eviction_404

        class _E(Exception):
            code = 404

        assert _looks_like_cache_eviction_404(_E("opaque"))

    def test_predicate_rejects_non_404_status(self):
        from components.llm_provider import _looks_like_cache_eviction_404

        class _E(Exception):
            status_code = 500

        assert not _looks_like_cache_eviction_404(
            _E("internal server error"),
        )

    def test_predicate_rejects_unrelated_message(self):
        from components.llm_provider import _looks_like_cache_eviction_404
        assert not _looks_like_cache_eviction_404(
            Exception("rate limit exceeded"),
        )
        assert not _looks_like_cache_eviction_404(
            Exception("model not available"),
        )
