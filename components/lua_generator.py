"""Unified LuaGenerator - plan Phase 3.D (supersedes TODO.md V7 "keep both generators").

One implementation, two modes:
  - fast: single LLM call, no harness loop, no escalation (daemon / batch)
  - iterative: harness feedback loop + Haiku->Sonnet->Opus escalation (workbench)

Canonical home: components/lua_generator.py (LOCKED).
Core direction: async (LOCKED). `agenerate(...)` is canonical.
`generate(...)` is a sync wrapper that fails fast if called from a running event loop.

LEGACY COMPATIBILITY: the `ClaudeLuaGenerator` shim and `LuaGenerationResult`
alias live alongside this class to keep existing callers and tests working
unchanged during the migration window. The `AgenticLuaGenerator` shim lives in
`components/agentic_lua_generator.py`.
"""
from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field, fields as _dc_fields
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Literal, Optional, Tuple

from components.llm_provider import (
    LLMProvider,
    LLMProviderError,
    LLMProviderPermanentError,
    LLMResponse,
    get_provider,
)
from components.lua_deploy_wrapper import wrap_for_observo

logger = logging.getLogger(__name__)


# ----- Normalized request / options / result -----


@dataclass
class SourceField:
    name: str
    type: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GenerationRequest:
    """Normalized request passed to every mode.

    Adapters construct from legacy call shapes:
      - from_legacy_args: ClaudeLuaGenerator.generate_lua(parser_id, parser_analysis, ocsf_schema=)
      - from_workbench_entry: AgenticLuaGenerator.generate(parser_entry, ...)
    """
    parser_id: str
    parser_name: str
    parser_analysis: Dict[str, Any]
    source_fields: List[SourceField]
    raw_examples: List[Any] = field(default_factory=list)
    historical_examples: List[Any] = field(default_factory=list)
    ocsf_schema: Optional[Dict[str, Any]] = None
    ocsf_class_uid: Optional[int] = None
    vendor: Optional[str] = None
    product: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def test_events(self) -> List[Any]:
        out: List[Any] = []
        seen = set()
        for item in list(self.raw_examples) + list(self.historical_examples):
            key = repr(item)
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
        return out

    @classmethod
    def from_legacy_args(
        cls,
        parser_id: str,
        parser_analysis: Dict[str, Any],
        ocsf_schema: Optional[Dict[str, Any]] = None,
    ) -> "GenerationRequest":
        raw_fields = (
            parser_analysis.get("source_fields")
            or parser_analysis.get("fields")
            or []
        )
        source_fields: List[SourceField] = []
        for f in raw_fields:
            if isinstance(f, dict):
                source_fields.append(SourceField(
                    name=f.get("name", ""),
                    type=f.get("type", ""),
                    metadata={k: v for k, v in f.items() if k not in ("name", "type")},
                ))
            elif isinstance(f, str):
                source_fields.append(SourceField(name=f, type=""))
        return cls(
            parser_id=parser_id,
            parser_name=parser_analysis.get("parser_name") or parser_id,
            parser_analysis=parser_analysis,
            source_fields=source_fields,
            ocsf_schema=ocsf_schema,
            ocsf_class_uid=(parser_analysis.get("ocsf_classification", {}) or {}).get("class_uid"),
            vendor=parser_analysis.get("vendor"),
            product=parser_analysis.get("product"),
        )

    @classmethod
    def from_workbench_entry(cls, entry: Dict[str, Any]) -> "GenerationRequest":
        parser_id = entry.get("parser_id") or entry.get("id") or entry.get("parser_name") or "unknown"
        raw_fields = entry.get("source_fields") or []
        source_fields: List[SourceField] = []
        for f in raw_fields:
            if isinstance(f, dict):
                source_fields.append(SourceField(
                    name=f.get("name", ""),
                    type=f.get("type", ""),
                    metadata={k: v for k, v in f.items() if k not in ("name", "type")},
                ))
            elif isinstance(f, str):
                source_fields.append(SourceField(name=f, type=""))
        return cls(
            parser_id=parser_id,
            parser_name=entry.get("parser_name") or parser_id,
            parser_analysis=entry.get("parser_analysis") or entry,
            source_fields=source_fields,
            raw_examples=list(entry.get("raw_examples") or []),
            historical_examples=list(entry.get("historical_examples") or []),
            ocsf_schema=entry.get("ocsf_schema"),
            ocsf_class_uid=entry.get("ocsf_class_uid"),
            vendor=entry.get("vendor"),
            product=entry.get("product"),
            metadata=entry.get("metadata") or {},
        )


@dataclass
class GenerationOptions:
    mode: Literal["fast", "iterative"] = "fast"
    max_iterations: int = 3
    target_score: int = 70
    escalation_ladder: List[str] = field(
        default_factory=lambda: ["haiku", "sonnet", "opus"]
    )
    provider_preference: Optional[str] = None
    cache_breakpoints: bool = True
    batch_size: int = 5
    max_concurrent: int = 3
    force_regenerate: bool = False


@dataclass
class GenerationResult:
    """Public compatibility facade - attribute AND mapping access.

    Field types match LEGACY LuaGenerationResult exactly for the first block.
    Opt-in structured data (harness_report, request, options) does not collide
    with legacy consumers.
    """
    # LEGACY OUTWARD SHAPE
    parser_id: str
    parser_name: str
    lua_code: str
    test_cases: str = ""
    performance_metrics: Dict[str, Any] = field(default_factory=dict)
    memory_analysis: str = ""
    deployment_notes: str = ""
    monitoring_recommendations: List[str] = field(default_factory=list)
    generated_at: str = ""
    confidence_score: float = 0.0

    # AGENTIC OUTWARD SHAPE
    confidence_grade: str = ""
    iterations: int = 1
    quality: str = "accepted"

    # AGENTIC METADATA
    model: str = ""
    ingestion_mode: str = ""
    ocsf_class_name: str = ""
    ocsf_class_uid: int = 0
    examples_used: int = 0
    generation_method: str = ""
    elapsed_seconds: float = 0.0
    vendor: Optional[str] = None
    product: Optional[str] = None
    error: Optional[str] = None

    # OPT-IN STRUCTURED DATA
    harness_report: Optional[Dict[str, Any]] = None
    request: Optional[GenerationRequest] = None
    options: Optional[GenerationOptions] = None
    success: bool = True

    # MAPPING COMPAT
    def __getitem__(self, key: str) -> Any:
        if not hasattr(self, key):
            raise KeyError(key)
        return getattr(self, key)

    def __contains__(self, key: str) -> bool:
        return hasattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def keys(self) -> Iterable[str]:
        return [f.name for f in _dc_fields(self)]

    def items(self) -> Iterable[Tuple[str, Any]]:
        return [(f.name, getattr(self, f.name)) for f in _dc_fields(self)]

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for f in _dc_fields(self):
            if f.name in ("request", "options"):
                continue
            out[f.name] = getattr(self, f.name)
        return out


# Legacy alias - GenerationResult is a strict superset of the old dataclass.
LuaGenerationResult = GenerationResult


# ----- The unified generator -----


class LuaGenerator:
    """One implementation, two modes (fast + iterative). Async canonical.

    Plan Phase 3.D. Consolidates the behavior of the legacy ClaudeLuaGenerator
    (fast mode) and AgenticLuaGenerator (iterative mode).
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        *,
        provider: Optional[LLMProvider] = None,
    ):
        self.config = config or {}
        anthropic_cfg = self.config.get("anthropic", {}) if isinstance(self.config, dict) else {}
        self.api_key = anthropic_cfg.get("api_key") or os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = anthropic_cfg.get("model", "claude-haiku-4-5-20251001")
        self.strong_model = anthropic_cfg.get("strong_model", "claude-sonnet-4-6")
        self.premium_model = anthropic_cfg.get("premium_model", "claude-opus-4-6")
        self.max_tokens = anthropic_cfg.get("max_tokens", 4000)
        self.temperature = anthropic_cfg.get("temperature", 0.0)
        # Lazy provider - only construct when actually used. Keeps HEAVY_LOADED clean.
        self._provider_override: Optional[LLMProvider] = provider
        self._provider_cached: Optional[LLMProvider] = None

    @property
    def _provider(self) -> LLMProvider:
        if self._provider_override is not None:
            return self._provider_override
        if self._provider_cached is None:
            self._provider_cached = get_provider(
                os.environ.get("LLM_PROVIDER_PREFERENCE", "anthropic"),
                api_key=self.api_key,
            )
        return self._provider_cached

    # ----- async canonical core -----

    async def agenerate(
        self,
        request: GenerationRequest,
        opts: Optional[GenerationOptions] = None,
    ) -> GenerationResult:
        opts = opts or GenerationOptions(mode="fast")
        if opts.mode == "fast":
            return await self._agenerate_fast(request, opts)
        elif opts.mode == "iterative":
            return await self._agenerate_iterative(request, opts)
        raise ValueError(f"unknown mode: {opts.mode!r}")

    def generate(
        self,
        request: GenerationRequest,
        opts: Optional[GenerationOptions] = None,
    ) -> GenerationResult:
        """Sync wrapper. Fails fast inside a running event loop."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.agenerate(request, opts))
        raise RuntimeError(
            "LuaGenerator.generate() cannot be called from a running event loop; "
            "use 'await agenerate(...)' or an async-aware entrypoint."
        )

    async def batch_generate_lua(
        self,
        requests: List[GenerationRequest],
        opts: Optional[GenerationOptions] = None,
    ) -> List[GenerationResult]:
        """Batch - N requests in, N results out. Failures have success=False
        and error populated. Legacy shim filters to success-only before
        returning to legacy callers.
        """
        opts = opts or GenerationOptions(mode="fast")
        sem = asyncio.Semaphore(max(1, opts.max_concurrent))

        async def _one(req: GenerationRequest) -> GenerationResult:
            async with sem:
                try:
                    return await self.agenerate(req, opts)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("batch item failed for %s", req.parser_id)
                    return GenerationResult(
                        parser_id=req.parser_id,
                        parser_name=req.parser_name,
                        lua_code="",
                        success=False,
                        error=str(exc),
                        generated_at=datetime.now(timezone.utc).isoformat(),
                        generation_method=opts.mode,
                    )

        return await asyncio.gather(*(_one(r) for r in requests))

    # ----- fast mode -----

    async def _agenerate_fast(
        self, request: GenerationRequest, opts: GenerationOptions
    ) -> GenerationResult:
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(request)
        model = self.model

        started = datetime.now(timezone.utc)
        try:
            resp: LLMResponse = await self._provider.agenerate(
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                model=model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                cache_breakpoints=opts.cache_breakpoints,
            )
        except LLMProviderPermanentError as exc:
            return self._failure_result(request, opts, started, str(exc), model)
        except LLMProviderError as exc:
            return self._failure_result(request, opts, started, f"transient: {exc}", model)

        lua_body = self._parse_lua_from_response(resp.text)
        wrapped = ""
        if lua_body:
            try:
                wrapped = wrap_for_observo(lua_body)
            except ValueError:
                wrapped = lua_body

        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        return GenerationResult(
            parser_id=request.parser_id,
            parser_name=request.parser_name,
            lua_code=wrapped,
            performance_metrics={"elapsed_seconds": elapsed, "usage": dict(resp.usage)},
            generated_at=datetime.now(timezone.utc).isoformat(),
            confidence_score=70.0 if wrapped else 0.0,
            confidence_grade="B" if wrapped else "F",
            iterations=1,
            quality="accepted" if wrapped else "below_threshold",
            model=resp.model,
            generation_method="fast",
            elapsed_seconds=elapsed,
            vendor=request.vendor,
            product=request.product,
            ocsf_class_uid=request.ocsf_class_uid or 0,
            request=request,
            options=opts,
            success=bool(wrapped),
            error=None if wrapped else "empty lua body after parse",
        )

    # ----- iterative mode -----

    async def _agenerate_iterative(
        self, request: GenerationRequest, opts: GenerationOptions
    ) -> GenerationResult:
        """Iterative mode - stub that delegates to fast mode for now.

        TODO: Phase 3.H follow-up will port the full harness-loop +
        Haiku->Sonnet->Opus escalation body from the legacy
        AgenticLuaGenerator._run_iteration_loop path. The legacy
        AgenticLuaGenerator shim in components/agentic_lua_generator.py
        still hosts the real iteration body during the migration window,
        so workbench callers keep the existing behavior unchanged.
        """
        result = await self._agenerate_fast(request, opts)
        result.generation_method = "iterative"
        result.iterations = max(result.iterations, 1)
        return result

    # ----- prompt + response helpers -----

    def _build_system_prompt(self) -> str:
        """Delegate to legacy module's SYSTEM_PROMPT so Phase 2 prompt sweeps
        are preserved."""
        try:
            from components.agentic_lua_generator import SYSTEM_PROMPT
            return SYSTEM_PROMPT
        except Exception:
            return "You are a Lua code generator for Observo.ai OCSF pipelines."

    def _build_user_prompt(self, request: GenerationRequest) -> str:
        lines = [
            f"Parser: {request.parser_name} ({request.parser_id})",
            f"Vendor: {request.vendor or 'unknown'} / Product: {request.product or 'unknown'}",
            f"OCSF class: {request.ocsf_class_uid or 'tbd'}",
            "Source fields:",
        ]
        for sf in request.source_fields[:30]:
            lines.append(f"  - {sf.name}: {sf.type or 'unknown'}")
        if request.raw_examples:
            lines.append("Sample events (raw):")
            for i, ex in enumerate(request.raw_examples[:3]):
                lines.append(f"  [{i}] <untrusted_sample>{ex}</untrusted_sample>")

        # Phase 3.F stub: prepend feedback corrections when available. Stubbed
        # for now - returns an empty list. Populating this is the next step.
        try:
            from components.web_ui.example_store import HarnessExampleStore  # noqa: F401
            corrections = self._read_feedback_corrections(request)
            if corrections:
                lines.append("Prior corrections to honor:")
                for idx, c in enumerate(corrections, 1):
                    lines.append(f"  ({idx}) {c}")
        except Exception:
            pass

        lines.append("Emit ONLY a Lua `function processEvent(event) ... end` body.")
        return "\n".join(lines)

    def _read_feedback_corrections(self, request: GenerationRequest) -> List[str]:
        """Phase 3.F stub - feedback read-loop.

        TODO: Phase 3.F follow-up will scan the feedback_system JSON log
        directory for corrections matching (ocsf_class_uid, vendor) and
        return them as few-shot pairs. For now this returns an empty list;
        the wire is in place so the stub can be swapped for the real call
        without touching callers.
        """
        return []

    def _parse_lua_from_response(self, text: str) -> str:
        if not text:
            return ""
        stripped = text.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            stripped = "\n".join(lines)
        return stripped.strip()

    def _failure_result(
        self,
        request: GenerationRequest,
        opts: GenerationOptions,
        started: datetime,
        error: str,
        model: str,
    ) -> GenerationResult:
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        return GenerationResult(
            parser_id=request.parser_id,
            parser_name=request.parser_name,
            lua_code="",
            performance_metrics={"elapsed_seconds": elapsed},
            generated_at=datetime.now(timezone.utc).isoformat(),
            confidence_score=0.0,
            confidence_grade="F",
            iterations=0,
            quality="below_threshold",
            model=model,
            generation_method=opts.mode,
            elapsed_seconds=elapsed,
            vendor=request.vendor,
            product=request.product,
            request=request,
            options=opts,
            success=False,
            error=error,
        )


# ----- Phase 3.E shim - legacy ClaudeLuaGenerator wrapper -----


class ClaudeLuaGenerator:
    """Legacy shim - delegates to LuaGenerator in fast mode.

    Preserves the existing public signature (constructor, generate_lua,
    batch_generate_lua) so current callers and tests work unchanged during
    the migration window. Will be deleted in a follow-up PR after callers
    migrate to `from components.lua_generator import LuaGenerator`.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._inner = LuaGenerator(config)
        # Legacy attribute reads preserved (for code that pokes at these)
        anthropic_cfg = (config or {}).get("anthropic", {}) if isinstance(config, dict) else {}
        self.model = anthropic_cfg.get("model", self._inner.model)
        self.max_tokens = anthropic_cfg.get("max_tokens", self._inner.max_tokens)
        self.temperature = anthropic_cfg.get("temperature", self._inner.temperature)

    async def generate_lua(
        self,
        parser_id: str,
        parser_analysis: Dict[str, Any],
        ocsf_schema: Optional[Dict[str, Any]] = None,
    ) -> GenerationResult:
        req = GenerationRequest.from_legacy_args(parser_id, parser_analysis, ocsf_schema=ocsf_schema)
        return await self._inner.agenerate(req, GenerationOptions(mode="fast"))

    async def batch_generate_lua(
        self,
        analyses: List[Dict[str, Any]],
        batch_size: int = 5,
        max_concurrent: int = 3,
    ) -> List[GenerationResult]:
        """Legacy batch API. Returns SUCCESS-ONLY filtered list."""
        requests = [
            GenerationRequest.from_legacy_args(a.get("parser_id", "unknown"), a)
            for a in analyses
        ]
        opts = GenerationOptions(
            mode="fast",
            batch_size=batch_size,
            max_concurrent=max_concurrent,
        )
        results = await self._inner.batch_generate_lua(requests, opts)
        return [r for r in results if r.success]

    def get_statistics(self) -> Dict[str, Any]:
        return {"success_rate": 0.0}
