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
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


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
    ) -> LLMResponse: ...

    def generate(
        self,
        system: str,
        messages: List[Dict[str, Any]],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        cache_breakpoints: bool = True,
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

        try:
            response = await client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_arg,
                messages=messages,
            )
        except (APIConnectionError, APITimeoutError) as exc:
            raise LLMProviderError(f"anthropic transient: {exc}") from exc
        except APIStatusError as exc:
            if exc.status_code in _RETRIABLE_STATUS:
                raise LLMProviderError(f"anthropic status {exc.status_code}") from exc
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
        )

    async def agenerate(
        self,
        system: str,
        messages: List[Dict[str, Any]],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        cache_breakpoints: bool = True,
    ) -> LLMResponse:
        return await _retry_with_backoff(
            self._agenerate_once,
            system, messages, model, max_tokens, temperature, cache_breakpoints,
        )

    generate = _sync_generate


# ----- OpenAIProvider -----

class OpenAIProvider:
    """OpenAI provider using the openai SDK (NOT requests.post).

    The current agentic_lua_generator.py::_call_openai uses requests.post —
    Phase 3.D deletes that. This provider is the replacement.
    """
    name = "openai"

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
    ) -> LLMResponse:
        try:
            from openai import APIConnectionError, APITimeoutError, APIStatusError
        except ImportError:
            class _Unreachable(Exception):
                status_code = 0
            APIStatusError = APIConnectionError = APITimeoutError = _Unreachable  # type: ignore
        client = self._ensure_client()

        # OpenAI takes a single messages list with the system as the first entry.
        full_messages = ([{"role": "system", "content": system}] if system else []) + messages

        try:
            response = await client.chat.completions.create(
                model=model,
                messages=full_messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except (APIConnectionError, APITimeoutError) as exc:
            raise LLMProviderError(f"openai transient: {exc}") from exc
        except APIStatusError as exc:
            if exc.status_code in _RETRIABLE_STATUS:
                raise LLMProviderError(f"openai status {exc.status_code}") from exc
            raise LLMProviderPermanentError(f"openai status {exc.status_code}: {exc}") from exc

        text = response.choices[0].message.content or ""
        usage = {}
        if response.usage:
            usage = {
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
            }

        return LLMResponse(
            text=text,
            model=model,
            usage=usage,
            cache_read_input_tokens=0,
            finish_reason=getattr(response.choices[0], "finish_reason", "") or "",
            provider="openai",
            raw=response,
        )

    async def agenerate(self, *args, **kwargs) -> LLMResponse:
        return await _retry_with_backoff(self._agenerate_once, *args, **kwargs)

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
    ) -> LLMResponse:
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

        # .text raises if blocked — check finish_reason first
        try:
            text = response.text or ""
            finish = "stop"
        except Exception:
            text = ""
            candidates = getattr(response, "candidates", None) or []
            finish = str(candidates[0].finish_reason) if candidates else "blocked"
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
