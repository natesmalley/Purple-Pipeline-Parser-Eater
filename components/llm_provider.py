"""LLM provider abstraction for Purple Pipeline Parser Eater.

Plan Phase 3.A — the canonical surface every generator uses.

Core direction: async. `agenerate(...)` is the primary method; `generate(...)`
is a sync wrapper that fails fast if called from a running event loop.
"""
from __future__ import annotations

import asyncio
import logging
import os
import random
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, Tuple, runtime_checkable

logger = logging.getLogger(__name__)


def _normalize_openai_reasoning_effort(
    model: str,
    effort: str,
) -> Tuple[Optional[str], Optional[str]]:
    """Normalize reasoning effort to a value supported by the target GPT-5 model.

    Returns ``(normalized_effort, warning_message)``. Empty effort returns
    ``(None, None)``. Unsupported efforts return ``(None, warning)``.
    Special case: ``"none"`` for pre-5.1 GPT-5 models is downgraded to
    ``"minimal"`` because the older Responses API endpoint rejects ``none``.

    FU12-DA-FU12 (REFUTE-1): relocated from agentic_lua_generator.py. The
    helper is provider-side logic — OpenAIProvider._agenerate_once_responses
    consumes it directly so the env-var wire-through doesn't depend on a
    cross-module circular import. agentic_lua_generator re-exports the same
    name for back-compat with tests that imported it from there.
    """
    normalized_model = (model or "").strip().lower()
    normalized_effort = (effort or "").strip().lower()
    if not normalized_effort:
        return None, None

    supported_efforts = {"minimal", "low", "medium", "high", "xhigh"}
    if normalized_model.startswith("gpt-5.1"):
        supported_efforts.add("none")

    if normalized_effort in supported_efforts:
        return normalized_effort, None

    if normalized_effort == "none" and normalized_model.startswith("gpt-5"):
        return "minimal", (
            f"OPENAI_REASONING_EFFORT=none is unsupported for {model}; "
            "using minimal instead"
        )

    return None, f"Ignoring unsupported OPENAI_REASONING_EFFORT={effort!r} for {model}"


def _settings_get(path: str):
    """Best-effort read from SettingsStore; None on failure."""
    try:
        from components.settings_store import get_global_store, SettingsStore
        inst = get_global_store()
        if inst is None:
            if not hasattr(_settings_get, "_inst"):
                _settings_get._inst = SettingsStore()
            inst = _settings_get._inst
        return inst.get(path)
    except Exception:
        return None


_RESPONSES_TRUNCATION_REASONS = {"max_output_tokens", "incomplete"}


@dataclass
class LLMResponse:
    """Normalized response from any LLM provider.

    Generator code reads `text` for the body; `model` for the actual model id
    used (useful for the escalation ladder); `usage` for token accounting;
    `cache_read_input_tokens` specifically for Anthropic prompt-cache verification
    (plan 3.B gates on this).
    """
    text: str
    model: str
    usage: Dict[str, int] = field(default_factory=dict)
    cache_read_input_tokens: int = 0
    finish_reason: str = ""
    provider: str = ""  # "anthropic" | "openai" | "gemini"
    raw: Optional[Any] = None  # opt-in: raw provider response for debugging
    # FU10 forward-compat fields (populated by FU11+; defaulted here so the
    # dataclass surface is stable for callers landing ahead of provider wiring).
    thinking_tokens: Optional[int] = None  # forward-compat only; Anthropic SDK does not reliably expose this; FU13 does NOT populate it; None means "we don't know" rather than "zero" (DA-Arch FU10 follow-up)
    cache_breakpoints_used: int = 0  # count of cache_control blocks the provider sent
    response_id: Optional[str] = None  # OpenAI Responses API id (for previous_response_id chaining)
    system_fingerprint: Optional[str] = None  # OpenAI chat-completions reproducibility identifier

    def is_truncated(self) -> bool:
        """Was this response cut off by a max_tokens limit?

        2026-04-28: cross-provider truncation detection. Each provider
        names its truncation finish_reason differently — this normalizes
        the check so callers (the iteration loop) react consistently
        instead of silently shipping broken Lua.

        Truncation values per provider:
          - Anthropic: ``stop_reason == "max_tokens"``
          - OpenAI chat-completions: ``finish_reason == "length"``
          - OpenAI Responses API: ``finish_reason`` in
                       ``_RESPONSES_TRUNCATION_REASONS`` (``max_output_tokens``
                       or ``incomplete``)
          - Gemini:    ``finish_reason`` includes ``"MAX_TOKENS"``
                       (str representation of the protobuf enum) OR ``"2"``
                       (the int value of the enum on some SDK versions)
        """
        fr = (self.finish_reason or "").strip()
        if not fr:
            return False
        upper = fr.upper()
        if "MAX_TOKENS" in upper:
            return True  # Anthropic + Gemini name match
        if upper == "LENGTH":
            return True  # OpenAI chat-completions
        if upper == "2":
            return True  # Gemini protobuf enum int form
        # OpenAI Responses API: finish_reason values like "max_output_tokens"
        # or "incomplete" (FU10 forward-compat for FU12 wiring).
        if self.provider == "openai" and fr in _RESPONSES_TRUNCATION_REASONS:
            return True
        return False


@runtime_checkable
class LLMProvider(Protocol):
    """Async-first provider protocol. All providers implement agenerate.

    generate() is a sync wrapper that asyncio.run()s agenerate; it raises
    RuntimeError if called from a running event loop. This matches the locked
    sync-wrapper semantics for the consolidated LuaGenerator in Phase 3.D.
    """
    name: str  # provider identifier, e.g. "anthropic"

    async def agenerate(
        self,
        system: str,
        messages: List[Dict[str, Any]],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        cache_breakpoints: bool = True,
        messages_split: Optional[Dict[str, str]] = None,
        previous_response_id: Optional[str] = None,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> LLMResponse: ...

    def generate(
        self,
        system: str,
        messages: List[Dict[str, Any]],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        cache_breakpoints: bool = True,
        messages_split: Optional[Dict[str, str]] = None,
        previous_response_id: Optional[str] = None,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> LLMResponse: ...


class LLMProviderError(Exception):
    """Base class for provider errors that SHOULD be retried (transient)."""


class LLMProviderPermanentError(Exception):
    """Base class for provider errors that should NOT be retried (permanent).

    Distinguishes 'model failed to produce valid output' from 'API is down'.
    The iteration loop in Phase 3.D uses this distinction to decide whether
    to escalate to a stronger model or just retry the same one.
    """


def _sync_generate(self, *args, **kwargs) -> "LLMResponse":
    """Sync wrapper: runs self.agenerate via asyncio.run.

    Fails fast if called from a running event loop — matches the locked
    semantics from plan Phase 3.D. Callers in an event loop must await
    agenerate(...) directly. Resolves self.agenerate at call time so test
    monkeypatches on the instance take effect.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # No running loop — safe to asyncio.run
        return asyncio.run(self.agenerate(*args, **kwargs))
    raise RuntimeError(
        "LLMProvider.generate() cannot be called from inside a running event loop. "
        "Use 'await provider.agenerate(...)' or an async-aware entrypoint instead."
    )


# ----- Retry + backoff -----

_RETRIABLE_STATUS = {429, 500, 502, 503, 504, 529}
_MAX_ATTEMPTS = 4
_MAX_WALL_CLOCK_SECONDS = 60.0
_PER_CALL_TIMEOUT_SECONDS = 120.0


async def _retry_with_backoff(coro_fn, *args, **kwargs):
    """Execute an async call with exponential backoff + jitter.

    Distinguishes retriable (transient) from permanent errors by exception type.
    LLMProviderError = retry. LLMProviderPermanentError = raise immediately.
    Any other exception is treated as permanent (conservative default).
    """
    start = time.monotonic()
    attempt = 0
    last_exc = None
    while attempt < _MAX_ATTEMPTS and time.monotonic() - start < _MAX_WALL_CLOCK_SECONDS:
        attempt += 1
        try:
            return await asyncio.wait_for(
                coro_fn(*args, **kwargs),
                timeout=_PER_CALL_TIMEOUT_SECONDS,
            )
        except LLMProviderPermanentError:
            raise
        except (LLMProviderError, asyncio.TimeoutError) as exc:
            last_exc = exc
            if attempt >= _MAX_ATTEMPTS:
                break
            backoff = min(2 ** attempt, 30) + random.uniform(0, 1)
            logger.warning(
                "LLM provider retry %d/%d after %.1fs: %s",
                attempt, _MAX_ATTEMPTS, backoff, exc,
            )
            await asyncio.sleep(backoff)
    raise LLMProviderError(
        f"LLM provider failed after {attempt} attempts: {last_exc}"
    )


# ----- AnthropicProvider -----

class AnthropicProvider:
    """Anthropic provider using the official anthropic SDK.

    Implements plan Phase 3.B prompt caching: marks the system prompt block
    with cache_control={"type": "ephemeral"} when cache_breakpoints=True.
    The iteration loop can verify the cache hit via
    LLMResponse.cache_read_input_tokens > 0 on the second iteration.
    """
    name = "anthropic"

    # Models where Anthropic has deprecated the `temperature` parameter
    # (reasoning-capable variants — server returns 400 invalid_request_error
    # `temperature is deprecated for this model.` if we pass it). Match by
    # prefix so future point releases pick up automatically.
    _NO_TEMPERATURE_PREFIXES = ("claude-opus-4-7",)

    # Runtime-discovered set: any model that returns the deprecation 400 once
    # gets cached here so subsequent calls in the same process skip the param
    # without a round trip. Class-level so it survives provider re-instantiation.
    _NO_TEMPERATURE_DISCOVERED: set = set()

    # FU13: models that support extended thinking via {"type": "adaptive"}.
    #
    # Per Anthropic's adaptive-thinking docs, ``claude-opus-4-7`` ONLY accepts
    # the adaptive form — passing ``{"type": "enabled", "budget_tokens": N}``
    # (the older shape) returns HTTP 400. ``claude-sonnet-4-6`` also routes
    # through adaptive thinking. The model self-allocates within its overall
    # response budget; we do NOT supply ``budget_tokens`` and we do NOT
    # partition ``max_tokens``. Match by prefix so future point releases
    # (e.g. claude-opus-4-7-20251101) pick up automatically.
    #
    # Anthropic also rejects requests that combine ``thinking`` and
    # ``temperature`` as incompatible — we unconditionally pop the temperature
    # param when thinking is added. See ``_agenerate_once`` below.
    #
    # We do NOT populate ``LLMResponse.thinking_tokens``: the Anthropic SDK
    # does not reliably expose ``response.usage.thinking_tokens`` across
    # versions. The dataclass field stays as forward-compat for a future
    # milestone.
    _THINKING_CAPABLE_PREFIXES = ("claude-opus-4-7", "claude-sonnet-4-6")

    @classmethod
    def _supports_temperature(cls, model: str) -> bool:
        if model in cls._NO_TEMPERATURE_DISCOVERED:
            return False
        return not any(model.startswith(p) for p in cls._NO_TEMPERATURE_PREFIXES)

    @classmethod
    def _thinking_supported(cls, model: str) -> bool:
        """True iff ``model`` accepts the ``thinking={"type": "adaptive"}`` param."""
        return any(model.startswith(p) for p in cls._THINKING_CAPABLE_PREFIXES)

    @classmethod
    def _max_output_tokens_for(cls, model: str) -> int:
        """Per-model output ceiling consumed by FU14's truncation retry.

        Anthropic publishes per-model output limits that are lower than the
        16k generic cap the iteration loop previously used. FU14 makes the
        truncation-retry doubling provider-aware so each model gets a
        ceiling matched to its actual capacity.

        Values per Anthropic model docs:
          - claude-opus-4-7   -> 32k
          - claude-sonnet-4-6 -> 64k
          - claude-haiku-4-5  -> 8192
          - other / unknown   -> 16k (legacy default; conservative)
        """
        normalized = (model or "").strip().lower()
        if normalized.startswith("claude-opus-4-7"):
            return 32000
        if normalized.startswith("claude-sonnet-4-6"):
            return 64000
        if normalized.startswith("claude-haiku-4-5"):
            return 8192
        return 16000

    def __init__(self, api_key: Optional[str] = None):
        # Lazy-import anthropic inside _ensure_client.
        if not api_key:
            api_key = _settings_get(
                "providers.anthropic.api_key")
        self._api_key = (
            api_key
            or os.environ.get("ANTHROPIC_API_KEY", "")
        )
        self._client = None

    def _ensure_client(self):
        if self._client is None:
            from anthropic import AsyncAnthropic  # lazy
            self._client = AsyncAnthropic(api_key=self._api_key)
        return self._client

    async def _agenerate_once(
        self,
        system: str,
        messages: List[Dict[str, Any]],
        model: str,
        max_tokens: int,
        temperature: float,
        cache_breakpoints: bool,
        messages_split: Optional[Dict[str, str]] = None,
    ) -> LLMResponse:
        # Lazy-import anthropic error types. If anthropic isn't installed (e.g.
        # test environment with a fully-mocked client), fall back to Exception
        # placeholders so the try/except below still parses.
        try:
            from anthropic import APIStatusError, APIConnectionError, APITimeoutError
        except ImportError:
            class _Unreachable(Exception):
                status_code = 0
            APIStatusError = APIConnectionError = APITimeoutError = _Unreachable  # type: ignore
        client = self._ensure_client()

        # Build the system field. With caching, wrap as a list of blocks so we
        # can attach cache_control to the final block (Anthropic's API shape).
        if cache_breakpoints and system:
            system_arg = [
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
        else:
            system_arg = system

        # FU14 P2-1: dual cache breakpoint. When the caller supplies
        # ``messages_split={"stable_prefix": ..., "delta_first_message": ...}``
        # AND ``cache_breakpoints=True``, build a fresh wire-format messages
        # list whose first user turn carries cache_control on the stable
        # prefix block.
        #
        # Caller invariant (enforced upstream in the generator helper):
        #   messages[0]["content"] == stable_prefix + delta_first_message
        #
        # Wire shape preserves semantic parity: concatenating stable_prefix +
        # delta_first_message produces the same model input as the unsplit
        # path. The split applies ONLY to messages[0]; messages[1:] pass
        # through unchanged as the structured-dict list they already are.
        cache_breakpoints_used = 1 if (cache_breakpoints and system) else 0
        if cache_breakpoints and messages_split is not None and messages:
            stable_prefix = messages_split.get("stable_prefix", "")
            delta_first_message = messages_split.get("delta_first_message", "")
            if delta_first_message:
                first_user_content: List[Dict[str, Any]] = [
                    {
                        "type": "text",
                        "text": stable_prefix,
                        "cache_control": {"type": "ephemeral"},
                    },
                    {"type": "text", "text": delta_first_message},
                ]
            else:
                first_user_content = [
                    {
                        "type": "text",
                        "text": stable_prefix,
                        "cache_control": {"type": "ephemeral"},
                    }
                ]
            messages_for_api: List[Dict[str, Any]] = [
                {
                    "role": messages[0].get("role", "user"),
                    "content": first_user_content,
                }
            ] + list(messages[1:])
            cache_breakpoints_used = (1 if system else 0) + 1
        else:
            messages_for_api = messages

        create_kwargs: Dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system_arg,
            "messages": messages_for_api,
        }
        if self._supports_temperature(model):
            create_kwargs["temperature"] = temperature

        # FU13: extended thinking for adaptive-thinking-capable models.
        #
        # Why adaptive-only: Anthropic's adaptive-thinking docs lock
        # ``claude-opus-4-7`` (and sibling reasoning models like
        # ``claude-sonnet-4-6``) to ``{"type": "adaptive"}``. The older
        # ``{"type": "enabled", "budget_tokens": N}`` shape 400s on opus-4-7.
        # The model self-allocates thinking within its overall response
        # budget; no ``budget_tokens`` knob, no ``max_tokens`` partitioning.
        #
        # Why we pop temperature: the API rejects requests combining
        # ``thinking`` and ``temperature`` as incompatible. Mechanism: after
        # adding ``thinking`` to ``create_kwargs``, unconditionally remove
        # ``temperature`` and log for audit.
        #
        # Why we don't surface ``thinking_tokens``: the Anthropic SDK does
        # not reliably expose ``response.usage.thinking_tokens`` across
        # versions. ``LLMResponse.thinking_tokens`` is left as ``None``
        # (forward-compat) to mean "we don't know"; a future milestone will
        # wire it once the SDK surface stabilizes.
        extended_thinking_setting = _settings_get(
            "providers.anthropic.extended_thinking"
        )
        extended_thinking_enabled = (
            True
            if extended_thinking_setting is None
            else bool(extended_thinking_setting)
        )
        if extended_thinking_enabled and self._thinking_supported(model):
            create_kwargs["thinking"] = {"type": "adaptive"}
            if "temperature" in create_kwargs:
                logger.debug(
                    "Anthropic %s with thinking=adaptive: omitting "
                    "`temperature` (API rejects the combination)",
                    model,
                )
                create_kwargs.pop("temperature", None)

        try:
            response = await client.messages.create(**create_kwargs)
        except (APIConnectionError, APITimeoutError) as exc:
            raise LLMProviderError(f"anthropic transient: {exc}") from exc
        except APIStatusError as exc:
            # Detect runtime "temperature is deprecated" 400 from a model not
            # in our static prefix list. Cache it, retry once without
            # temperature, then on success continue. This makes us robust to
            # Anthropic deprecating the param on additional models without
            # requiring a code change.
            msg_lower = str(exc).lower()
            if (
                exc.status_code == 400
                and "temperature" in msg_lower
                and "deprecat" in msg_lower
                and "temperature" in create_kwargs
            ):
                type(self)._NO_TEMPERATURE_DISCOVERED.add(model)
                create_kwargs.pop("temperature", None)
                logger.warning(
                    "Anthropic model %s rejected `temperature`; retrying without "
                    "and caching for future calls in this process.",
                    model,
                )
                try:
                    response = await client.messages.create(**create_kwargs)
                except (APIConnectionError, APITimeoutError) as exc2:
                    raise LLMProviderError(f"anthropic transient: {exc2}") from exc2
                except APIStatusError as exc2:
                    if exc2.status_code in _RETRIABLE_STATUS:
                        raise LLMProviderError(f"anthropic status {exc2.status_code}") from exc2
                    raise LLMProviderPermanentError(f"anthropic status {exc2.status_code}: {exc2}") from exc2
            elif exc.status_code in _RETRIABLE_STATUS:
                raise LLMProviderError(f"anthropic status {exc.status_code}") from exc
            else:
                raise LLMProviderPermanentError(f"anthropic status {exc.status_code}: {exc}") from exc

        text_parts = []
        for block in response.content:
            if getattr(block, "type", None) == "text":
                text_parts.append(block.text)
        text = "".join(text_parts)

        usage = {}
        cache_read = 0
        if response.usage:
            usage = {
                "input_tokens": getattr(response.usage, "input_tokens", 0),
                "output_tokens": getattr(response.usage, "output_tokens", 0),
            }
            cache_read = getattr(response.usage, "cache_read_input_tokens", 0) or 0
            if cache_read:
                usage["cache_read_input_tokens"] = cache_read

        return LLMResponse(
            text=text,
            model=model,
            usage=usage,
            cache_read_input_tokens=cache_read,
            finish_reason=getattr(response, "stop_reason", "") or "",
            provider="anthropic",
            raw=response,
            cache_breakpoints_used=cache_breakpoints_used,
        )

    async def agenerate(
        self,
        system: str,
        messages: List[Dict[str, Any]],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        cache_breakpoints: bool = True,
        messages_split: Optional[Dict[str, str]] = None,
        previous_response_id: Optional[str] = None,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> LLMResponse:
        # FU14 P2-1: ``messages_split`` is now forwarded to ``_agenerate_once``
        # so the dual cache breakpoint (system block + first-user-stable
        # block) lands on the wire. ``previous_response_id`` and
        # ``response_format`` are OpenAI-only and remain accepted-and-ignored
        # here for cross-provider Protocol parity.
        return await _retry_with_backoff(
            self._agenerate_once,
            system, messages, model, max_tokens, temperature, cache_breakpoints,
            messages_split=messages_split,
        )

    generate = _sync_generate


# ----- OpenAIProvider -----

class OpenAIProvider:
    """OpenAI provider using the openai SDK (NOT requests.post).

    The current agentic_lua_generator.py::_call_openai uses requests.post —
    Phase 3.D deletes that. This provider is the replacement.

    FU11 mirrors AnthropicProvider's reasoning-model parameter handling:
      - reasoning families (gpt-5*, o1*, o3*, o4*) reject `temperature` (server
        returns HTTP 400 with "temperature is unsupported"/"is deprecated"); we
        omit the param up front via a static prefix list, and discover any
        additional offenders at runtime.
      - the same families reject `max_tokens` and require `max_completion_tokens`
        instead. Same static-prefix + runtime-discovered split applies.
    Legacy gpt-4* / gpt-3.5* models keep the original `max_tokens` + `temperature`
    pair untouched.
    """
    name = "openai"

    # FU12: Responses API target families. The reasoning-capable families
    # (gpt-5*, o1*, o3*, o4*) ship through `client.responses.create` rather
    # than `client.chat.completions.create`. Static-prefix list mirrors the
    # NO_TEMPERATURE_PREFIXES set so they evolve together; legacy gpt-4*
    # continue on chat-completions exactly as FU11 left them.
    _RESPONSES_API_PREFIXES = ("gpt-5", "o1", "o3", "o4")

    # Reasoning-capable families where the OpenAI server rejects the legacy
    # `temperature` param. Match by prefix so future point releases pick up
    # automatically (gpt-5.4-mini, o1-pro, o3-mini-2025-..., etc.).
    _NO_TEMPERATURE_PREFIXES = ("gpt-5", "o1", "o3", "o4")

    # Runtime-discovered set: any model that returns the deprecation 400 once
    # gets cached here so subsequent calls in the same process skip the param
    # without a round trip. Class-level so it survives provider re-instantiation.
    _NO_TEMPERATURE_DISCOVERED: set = set()

    # Reasoning-capable families that require `max_completion_tokens` instead
    # of `max_tokens`. Same families today, separate constant so we can diverge
    # cleanly if OpenAI splits the deprecation timelines later.
    _NO_MAX_TOKENS_PREFIXES = ("gpt-5", "o1", "o3", "o4")

    # Runtime-discovered set for the max_tokens deprecation, parallel to the
    # temperature discovery cache.
    _NO_MAX_TOKENS_DISCOVERED: set = set()

    # FU11 R1+R2: runtime rejection-message detection. Two SEPARATE regexes —
    # the temperature and max_tokens deprecations evolve on different OpenAI
    # timelines, so a phrasing fix to one branch must not spuriously broaden
    # the other. Word-boundary anchoring (\b) avoids substring-subsumption
    # bugs (e.g. plain "supported" matching "this region is supported" and
    # caching unrelated 400s as deprecation hits).
    _TEMPERATURE_REJECTION_RE = re.compile(
        r"\b(?:unsupported|deprecat|does not support|not supported)\b",
        re.IGNORECASE,
    )
    _MAX_TOKENS_REJECTION_RE = re.compile(
        r"\b(?:unsupported|deprecat|does not support|not supported"
        r"|use 'max_completion_tokens')\b",
        re.IGNORECASE,
    )

    @classmethod
    def _supports_temperature(cls, model: str) -> bool:
        if model in cls._NO_TEMPERATURE_DISCOVERED:
            return False
        return not any(model.startswith(p) for p in cls._NO_TEMPERATURE_PREFIXES)

    @classmethod
    def _supports_legacy_max_tokens(cls, model: str) -> bool:
        if model in cls._NO_MAX_TOKENS_DISCOVERED:
            return False
        return not any(model.startswith(p) for p in cls._NO_MAX_TOKENS_PREFIXES)

    @classmethod
    def _use_responses_api(cls, model: str) -> bool:
        """Decide whether to route through ``client.responses.create``.

        FU12: GPT-5 family + reasoning models (o1/o3/o4) ship through the
        Responses API. Legacy gpt-4* / gpt-3.5* keep going through
        ``client.chat.completions.create``.

        ``OPENAI_API_MODE`` env var lets operators force one path:
          - ``responses`` -> always Responses API (overrides the prefix list)
          - ``chat`` / ``chat_completions`` -> always chat-completions
          - any other value (or unset) -> auto, by model prefix
        """
        api_mode = (os.environ.get("OPENAI_API_MODE") or "auto").strip().lower()
        if api_mode == "responses":
            return True
        if api_mode in {"chat", "chat_completions"}:
            return False
        normalized = (model or "").strip().lower()
        return any(normalized.startswith(p) for p in cls._RESPONSES_API_PREFIXES)

    @classmethod
    def _max_output_tokens_for(cls, model: str) -> int:
        """Per-model output ceiling consumed by FU14's truncation retry.

        gpt-5* / o1* / o3* / o4* support up to 32k output tokens; legacy
        chat-completions families cap at 16k. FU12 wires the predicate; the
        actual ``max_tokens`` doubling on truncation is FU14 work.
        """
        normalized = (model or "").strip().lower()
        if any(normalized.startswith(p) for p in ("gpt-5", "o1", "o3", "o4")):
            return 32000
        return 16000

    def __init__(self, api_key: Optional[str] = None):
        if not api_key:
            api_key = _settings_get(
                "providers.openai.api_key")
        self._api_key = (
            api_key
            or os.environ.get("OPENAI_API_KEY", "")
        )
        self._client = None

    def _ensure_client(self):
        if self._client is None:
            from openai import AsyncOpenAI  # lazy
            self._client = AsyncOpenAI(api_key=self._api_key)
        return self._client

    async def _agenerate_once(
        self,
        system: str,
        messages: List[Dict[str, Any]],
        model: str,
        max_tokens: int,
        temperature: float,
        cache_breakpoints: bool,  # unused for OpenAI — no explicit cache API in v1
        messages_split: Optional[Dict[str, str]] = None,
        previous_response_id: Optional[str] = None,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> LLMResponse:
        # FU12 dispatch: gpt-5*/o1*/o3*/o4* go through the Responses API,
        # legacy gpt-4* / gpt-3.5* keep going through chat-completions.
        if self._use_responses_api(model):
            return await self._agenerate_once_responses(
                system=system,
                messages=messages,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                previous_response_id=previous_response_id,
                response_format=response_format,
            )
        return await self._agenerate_once_chat_completions(
            system=system,
            messages=messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    async def _agenerate_once_chat_completions(
        self,
        system: str,
        messages: List[Dict[str, Any]],
        model: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        """Legacy chat-completions path. FU11 surface preserved verbatim."""
        try:
            from openai import APIConnectionError, APITimeoutError, APIStatusError
        except ImportError:
            class _Unreachable(Exception):
                status_code = 0
            APIStatusError = APIConnectionError = APITimeoutError = _Unreachable  # type: ignore
        client = self._ensure_client()

        # OpenAI takes a single messages list with the system as the first entry.
        full_messages = ([{"role": "system", "content": system}] if system else []) + messages

        create_kwargs: Dict[str, Any] = {
            "model": model,
            "messages": full_messages,
        }
        # FU11 P0-2: reasoning-family models reject `max_tokens`; switch to
        # `max_completion_tokens`. Static prefix list + runtime-discovered
        # cache mirror the temperature handling.
        if self._supports_legacy_max_tokens(model):
            create_kwargs["max_tokens"] = max_tokens
        else:
            create_kwargs["max_completion_tokens"] = max_tokens
        # FU11 P0-1: reasoning-family models reject `temperature`; omit it.
        if self._supports_temperature(model):
            create_kwargs["temperature"] = temperature

        async def _do_call() -> Any:
            return await client.chat.completions.create(**create_kwargs)

        try:
            response = await _do_call()
        except (APIConnectionError, APITimeoutError) as exc:
            raise LLMProviderError(f"openai transient: {exc}") from exc
        except APIStatusError as exc:
            # Detect runtime parameter rejections from a model not yet in our
            # static prefix lists. Cache the model + retry once with the
            # offending param removed (or swapped, in the max_tokens case).
            # This makes us robust to OpenAI extending the deprecation to
            # additional models without requiring a code change.
            msg = str(exc)
            msg_lower = msg.lower()
            retried = False
            # FU11 R1+R2: detect parameter rejection wording with two SEPARATE
            # word-boundary regexes (class-level constants). Real-world gpt-5
            # 400s say e.g.
            #   "'temperature' does not support 0.7 with this model. Only the
            #    default (1) value is supported."
            # which contains neither "unsupported" nor "deprecat" — the
            # broader patterns + \b anchoring catch it without subsuming
            # innocuous "...is supported..." prose.
            if exc.status_code == 400:
                if (
                    "temperature" in msg_lower
                    and type(self)._TEMPERATURE_REJECTION_RE.search(msg) is not None
                    and "temperature" in create_kwargs
                ):
                    type(self)._NO_TEMPERATURE_DISCOVERED.add(model)
                    create_kwargs.pop("temperature", None)
                    logger.warning(
                        "OpenAI model %s rejected `temperature`; retrying without "
                        "and caching for future calls in this process.",
                        model,
                    )
                    retried = True
                if (
                    "max_tokens" in msg_lower
                    and type(self)._MAX_TOKENS_REJECTION_RE.search(msg) is not None
                    and "max_tokens" in create_kwargs
                ):
                    type(self)._NO_MAX_TOKENS_DISCOVERED.add(model)
                    swap_value = create_kwargs.pop("max_tokens")
                    create_kwargs["max_completion_tokens"] = swap_value
                    logger.warning(
                        "OpenAI model %s rejected `max_tokens`; retrying with "
                        "`max_completion_tokens` and caching for future calls.",
                        model,
                    )
                    retried = True
            if retried:
                try:
                    response = await _do_call()
                except (APIConnectionError, APITimeoutError) as exc2:
                    raise LLMProviderError(f"openai transient: {exc2}") from exc2
                except APIStatusError as exc2:
                    if exc2.status_code in _RETRIABLE_STATUS:
                        raise LLMProviderError(f"openai status {exc2.status_code}") from exc2
                    raise LLMProviderPermanentError(f"openai status {exc2.status_code}: {exc2}") from exc2
            elif exc.status_code in _RETRIABLE_STATUS:
                raise LLMProviderError(f"openai status {exc.status_code}") from exc
            else:
                raise LLMProviderPermanentError(f"openai status {exc.status_code}: {exc}") from exc

        text = response.choices[0].message.content or ""
        usage = {}
        if response.usage:
            usage = {
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
            }
        system_fingerprint = getattr(response, "system_fingerprint", None)

        return LLMResponse(
            text=text,
            model=model,
            usage=usage,
            cache_read_input_tokens=0,
            finish_reason=getattr(response.choices[0], "finish_reason", "") or "",
            provider="openai",
            raw=response,
            system_fingerprint=system_fingerprint,
        )

    async def _agenerate_once_responses(
        self,
        system: str,
        messages: List[Dict[str, Any]],
        model: str,
        max_tokens: int,
        temperature: float,
        previous_response_id: Optional[str] = None,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> LLMResponse:
        """FU12 Responses API path for gpt-5/o1/o3/o4 family.

        Wire-format notes:
          - ``instructions=`` carries what was the system role in chat-completions
          - ``input=`` is a list of role/content pairs (no system entry mixed in)
          - ``max_output_tokens=`` replaces ``max_tokens``
          - ``previous_response_id=`` chains turns server-side
          - **CRITICAL**: structured-output is configured via
            ``text={"format": response_format}``, NOT a top-level
            ``response_format=`` kwarg. The SDK rejects the chat-completions
            shape on the Responses API.

        The FU11 deprecation-cache-and-retry blocks DO NOT apply here: the
        Responses API uses ``max_output_tokens`` (not deprecated for any
        model) and reasoning-family models reject ``temperature`` outright,
        so the static-prefix predicate is sufficient.
        """
        try:
            from openai import APIConnectionError, APITimeoutError, APIStatusError
        except ImportError:
            class _Unreachable(Exception):
                status_code = 0
            APIStatusError = APIConnectionError = APITimeoutError = _Unreachable  # type: ignore
        client = self._ensure_client()

        # Responses API takes input as a list of role/content pairs without
        # a leading system entry — the system prompt rides on `instructions=`.
        messages_as_input = [
            {"role": m.get("role", "user"), "content": m.get("content", "")}
            for m in messages
        ]

        create_kwargs: Dict[str, Any] = {
            "model": model,
            "input": messages_as_input,
            "max_output_tokens": max_tokens,
        }
        if system:
            create_kwargs["instructions"] = system
        if previous_response_id is not None:
            create_kwargs["previous_response_id"] = previous_response_id
        if response_format is not None:
            # CRITICAL: nest under text.format, not top-level response_format.
            create_kwargs["text"] = {"format": response_format}
        # Reasoning families reject temperature; the static prefix list (which
        # _use_responses_api() consults) is the same set as
        # _NO_TEMPERATURE_PREFIXES, so in practice this stays False for all
        # callers that land here. Forced-mode (OPENAI_API_MODE=responses) on
        # a legacy model is the corner case where supports_temperature is True.
        if self._supports_temperature(model):
            create_kwargs["temperature"] = temperature

        # FU12-DA-FU12 (REFUTE-1): operator-tunable Responses API knobs.
        # Pre-FU12 these flowed through _build_openai_responses_request in
        # agentic_lua_generator.py; that path is deleted, so the unified
        # provider now reads them directly. Both env vars are GPT-5-only
        # per the pre-FU12 behaviour — non-gpt-5 reasoning families (o1/
        # o3/o4) historically didn't apply them.
        normalized_model = (model or "").strip().lower()
        if normalized_model.startswith("gpt-5"):
            reasoning_effort = (
                os.environ.get("OPENAI_REASONING_EFFORT") or ""
            ).strip().lower()
            text_verbosity = (
                os.environ.get("OPENAI_TEXT_VERBOSITY") or ""
            ).strip().lower()
            if reasoning_effort:
                normalized_effort, warning = _normalize_openai_reasoning_effort(
                    model, reasoning_effort,
                )
                if warning:
                    logger.warning(warning)
                if normalized_effort:
                    create_kwargs["reasoning"] = {"effort": normalized_effort}
            if text_verbosity:
                # Merge with any existing text config (e.g. response_format
                # may already have populated text["format"]). The pre-FU12
                # builder applied verbosity unconditionally only when
                # response_format was absent; we now merge so callers get
                # both knobs simultaneously.
                existing_text = create_kwargs.get("text") or {}
                existing_text["verbosity"] = text_verbosity
                create_kwargs["text"] = existing_text

        try:
            response = await client.responses.create(**create_kwargs)
        except (APIConnectionError, APITimeoutError) as exc:
            raise LLMProviderError(f"openai responses transient: {exc}") from exc
        except APIStatusError as exc:
            if exc.status_code in _RETRIABLE_STATUS:
                raise LLMProviderError(
                    f"openai responses status {exc.status_code}"
                ) from exc
            raise LLMProviderPermanentError(
                f"openai responses status {exc.status_code}: {exc}"
            ) from exc

        # Extract text. SDK's response.output_text is the preferred shortcut;
        # fall back to walking response.output[i].content[j].text for older
        # SDK shapes or non-text content blocks.
        text = ""
        output_text = getattr(response, "output_text", None)
        if isinstance(output_text, str) and output_text:
            text = output_text
        else:
            chunks: List[str] = []
            output = getattr(response, "output", None) or []
            for item in output:
                content = getattr(item, "content", None) or []
                for block in content:
                    block_text = getattr(block, "text", None)
                    if isinstance(block_text, str) and block_text:
                        chunks.append(block_text)
            text = "\n".join(chunks)

        # Usage: Responses API names it input_tokens / output_tokens (matches
        # Anthropic shape). Different from chat-completions'
        # prompt_tokens / completion_tokens.
        usage: Dict[str, int] = {}
        cache_read = 0
        usage_obj = getattr(response, "usage", None)
        if usage_obj is not None:
            input_tokens = getattr(usage_obj, "input_tokens", 0) or 0
            output_tokens = getattr(usage_obj, "output_tokens", 0) or 0
            usage = {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }
            # FU18 will surface cached_tokens through cache_read_input_tokens;
            # populate when present so the field is correct now and FU18 just
            # adds verification.
            details = getattr(usage_obj, "input_tokens_details", None)
            if details is not None:
                cached = getattr(details, "cached_tokens", 0) or 0
                if cached:
                    cache_read = cached
                    usage["cache_read_input_tokens"] = cached

        # Finish-reason mapping: Responses API exposes incomplete_details only
        # when the call was cut off. Map "max_output_tokens" through verbatim
        # so LLMResponse.is_truncated() (FU10) fires.
        finish_reason = "stop"
        incomplete = getattr(response, "incomplete_details", None)
        if incomplete is not None:
            reason = getattr(incomplete, "reason", None)
            if isinstance(reason, str) and reason:
                finish_reason = reason

        response_id = getattr(response, "id", None)

        return LLMResponse(
            text=text,
            model=model,
            usage=usage,
            cache_read_input_tokens=cache_read,
            finish_reason=finish_reason,
            provider="openai",
            raw=response,
            response_id=response_id,
        )

    async def agenerate(
        self,
        system: str,
        messages: List[Dict[str, Any]],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        cache_breakpoints: bool = True,
        messages_split: Optional[Dict[str, str]] = None,
        previous_response_id: Optional[str] = None,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> LLMResponse:
        # DA-Architecture FU11 follow-up: explicit typed signature replaces
        # the previous `*args, **kwargs` form so OpenAIProvider matches the
        # AnthropicProvider Protocol shape exactly. FU12 will consume
        # previous_response_id + response_format when routing to the
        # Responses API; FU14 wires messages_split. They pass through to
        # _agenerate_once today as accept-and-ignore kwargs.
        return await _retry_with_backoff(
            self._agenerate_once,
            system, messages, model, max_tokens, temperature, cache_breakpoints,
            messages_split=messages_split,
            previous_response_id=previous_response_id,
            response_format=response_format,
        )

    generate = _sync_generate


# ----- GeminiProvider -----

class GeminiProvider:
    """Google Gemini provider using google-generativeai.

    Gemini gotchas (from plan Phase 3.A):
      - System prompt passes as system_instruction=, NOT as a message with role=system
      - Content shape is contents=[{role, parts:[{text}]}]
      - Safety filters aggressive by default — set permissive for HARASSMENT,
        HATE_SPEECH, SEXUALLY_EXPLICIT, DANGEROUS_CONTENT. Security-log content
        (IOCs, malware hashes, credential names) will otherwise be silently blocked.
      - .text raises if blocked — wrap in try/except and check finish_reason.
    """
    name = "gemini"

    @classmethod
    def _max_output_tokens_for(cls, model: str) -> int:
        """Per-model output ceiling consumed by FU14's truncation retry.

        Gemini 2.5 Pro publishes a 65k output window; 2.5 Flash caps at 16k.
        Older / unknown models fall back to the conservative 16k legacy
        default that the iteration loop used pre-FU14.
        """
        normalized = (model or "").strip().lower()
        if normalized.startswith("gemini-2.5-pro"):
            return 65536
        if normalized.startswith("gemini-2.5-flash"):
            return 16384
        return 16000

    def __init__(self, api_key: Optional[str] = None):
        if not api_key:
            api_key = _settings_get(
                "providers.gemini.api_key")
        self._api_key = (
            api_key
            or os.environ.get("GEMINI_API_KEY", "")
        )
        self._genai = None

    def _ensure_client(self):
        if self._genai is None:
            import google.generativeai as genai  # lazy
            genai.configure(api_key=self._api_key)
            self._genai = genai
        return self._genai

    async def _agenerate_once(
        self,
        system: str,
        messages: List[Dict[str, Any]],
        model: str,
        max_tokens: int,
        temperature: float,
        cache_breakpoints: bool,  # Gemini has caching.CachedContent but v1 ships without it
        messages_split: Optional[Dict[str, str]] = None,
        previous_response_id: Optional[str] = None,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> LLMResponse:
        # FU10 foundation kwargs accepted but not consumed. Gemini-specific
        # wiring (if any) is out of scope for the multi-provider workflow plan.
        genai = self._ensure_client()

        # Gemini safety settings: permissive for security content
        safety = [
            {"category": c, "threshold": "BLOCK_NONE"}
            for c in ("HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH",
                      "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT")
        ]

        gemini_contents = []
        for m in messages:
            role = "user" if m.get("role") == "user" else "model"
            gemini_contents.append({"role": role, "parts": [{"text": m.get("content", "")}]})

        try:
            model_obj = genai.GenerativeModel(
                model_name=model,
                system_instruction=system or None,
                safety_settings=safety,
                generation_config={
                    "max_output_tokens": max_tokens,
                    "temperature": temperature,
                },
            )
            # genai.GenerativeModel.generate_content is sync; use the async variant
            response = await asyncio.to_thread(
                model_obj.generate_content, gemini_contents
            )
        except Exception as exc:
            # Gemini doesn't distinguish retriable cleanly — treat all as transient
            raise LLMProviderError(f"gemini error: {exc}") from exc

        # 2026-04-28: ALWAYS read finish_reason from candidates, not just on
        # exception. Gemini returns truncated text successfully when it hits
        # max_output_tokens — the previous code labelled that "stop" and lost
        # the truncation signal, so the iteration loop wrapped + shipped
        # broken Lua. Now finish_reason flows back to the caller.
        text = ""
        finish = "stop"
        candidates = getattr(response, "candidates", None) or []
        if candidates:
            finish = str(candidates[0].finish_reason)
        try:
            text = response.text or ""
        except Exception:
            text = ""
            if "BLOCKED" in finish.upper() or "SAFETY" in finish.upper():
                raise LLMProviderPermanentError(
                    f"gemini blocked content (finish_reason={finish}). "
                    "Check safety_settings if this is security-log data."
                )

        usage = {}
        if getattr(response, "usage_metadata", None):
            usage = {
                "input_tokens": response.usage_metadata.prompt_token_count,
                "output_tokens": response.usage_metadata.candidates_token_count,
            }

        return LLMResponse(
            text=text,
            model=model,
            usage=usage,
            cache_read_input_tokens=0,
            finish_reason=finish,
            provider="gemini",
            raw=response,
        )

    async def agenerate(self, *args, **kwargs) -> LLMResponse:
        return await _retry_with_backoff(self._agenerate_once, *args, **kwargs)

    generate = _sync_generate


# ----- Factory -----

def get_provider(name: str, api_key: Optional[str] = None) -> LLMProvider:
    """Return a provider instance by name.

    Respects LLM_PROVIDER_PREFERENCE env var if name is 'default'.
    """
    if name == "default":
        name = (
            _settings_get("providers.active")
            or os.environ.get(
                "LLM_PROVIDER_PREFERENCE", "anthropic")
        )
    if name == "anthropic":
        return AnthropicProvider(api_key=api_key)
    if name == "openai":
        return OpenAIProvider(api_key=api_key)
    if name == "gemini":
        return GeminiProvider(api_key=api_key)
    raise ValueError(f"unknown provider: {name!r}")
