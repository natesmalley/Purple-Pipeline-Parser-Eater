"""Standalone dataplane YAML builder - plan Phase 5.A.

Emits snake_case Vector YAML for the Observo standalone dataplane binary
(Rust fork of timberio/vector 0.44.7 / dbac53e / 2025-10-15). This is the
SIBLING to components/observo_pipeline_builder.py - that file targets the
SaaS REST control plane (camelCase) and must NOT be mutated to snake_case.

Runtime reality (verified against dataplane.amd64 binary symbol audit):
- type: lua (NOT lua_script)
- version: "3" (quoted string)
- source: | (the Lua body - NOT luaScript, NOT script)
- FORBIDDEN: drop_on_error, drop_on_abort, reroute_dropped (REMAP-only)
- FORBIDDEN: bypass_transform, metric_event as YAML fields

See CLAUDE.md "Standalone console wire format" for the authoritative shape.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

# Forbidden key sets per Phase 5.A
_FORBIDDEN_V3_LUA_TRANSFORM_KEYS = frozenset({
    "lua_script", "script",  # wrong key for v3 lua transform body
    "bypass_transform", "metric_event",  # not in binary
    "drop_on_error", "drop_on_abort", "reroute_dropped",  # REMAP-only
    "rpc_domain",  # binary uses http_cfgs
})

# Path sanitization - reject absolute developer paths
_ABSOLUTE_DEV_PATH_RE = re.compile(r"(?:/Users/|/home/[^/]+/|[A-Za-z]:\\|\.\.)")

_DEFAULT_LUA_DIR = "/etc/dataplane/ocsf"


class DataplaneYamlBuildError(ValueError):
    """Raised when the builder is asked to emit something the binary would reject."""


@dataclass
class LuaTransform:
    """Snake_case Vector lua transform (lv3 v3)."""
    id: str                                  # YAML key
    inputs: List[str]
    source: str                              # the Lua body - already wrapped via wrap_for_observo
    parallelism: int = 1
    search_dirs: List[str] = field(default_factory=list)
    process_fn: str = "process"              # the function name to invoke
    version: Literal["2", "3"] = "3"

    def to_yaml_dict(self) -> Dict[str, Any]:
        """Emit the dict shape a YAML serializer would write."""
        if self.version == "3":
            out: Dict[str, Any] = {
                "type": "lua",
                "version": "3",
                "inputs": list(self.inputs),
                "parallelism": self.parallelism,
                "process": self.process_fn,
                "source": self.source,
            }
            if self.search_dirs:
                out["search_dirs"] = list(self.search_dirs)
            return out
        elif self.version == "2":
            # v2 shape: hooks + timers + metric_tag_values (per CLAUDE.md binary audit)
            return {
                "type": "lua",
                "version": "2",
                "inputs": list(self.inputs),
                "hooks": {
                    "process": self.process_fn,
                },
                "source": self.source,
            }
        raise DataplaneYamlBuildError(f"unsupported version: {self.version}")


@dataclass
class SplunkHecSink:
    """SentinelOne HEC sink - modeled as type: splunk_hec_logs per plan 5.B."""
    id: str
    inputs: List[str]
    endpoint: str
    default_token: str                       # caller responsibility to redact if published
    # timestamp_key: omitted deliberately per plan 5.B (the production sample has
    # `timestamp_key: '""'` which is a two-char key name that silently disables
    # extraction - we do not copy that bug; we omit the key to inherit default behavior)
    compression: str = "gzip"
    endpoint_target: str = "event"
    path: str = "/services/collector/event?isParsed=true"

    def to_yaml_dict(self) -> Dict[str, Any]:
        return {
            "type": "splunk_hec_logs",
            "inputs": list(self.inputs),
            "endpoint": self.endpoint,
            "endpoint_target": self.endpoint_target,
            "path": self.path,
            "default_token": self.default_token,
            "compression": self.compression,
            "encoding": {"codec": "json", "json": {"pretty": False}},
            "acknowledgements": {"enabled": False},
            "batch": {"max_bytes": 6000000, "max_events": 50000, "timeout_secs": 1},
            "buffer": {"type": "memory", "max_events": 100000},
            "request": {
                "concurrency": "adaptive",
                "timeout_secs": 60,
                "retry_initial_backoff_secs": 1,
                "retry_max_duration_secs": 3600,
            },
        }


def _sanitize_search_dirs(search_dirs: List[str]) -> List[str]:
    """Reject absolute developer paths. Drive from OBSERVO_LUA_DIR env var."""
    if not search_dirs:
        return [os.environ.get("OBSERVO_LUA_DIR", _DEFAULT_LUA_DIR)]
    for d in search_dirs:
        if _ABSOLUTE_DEV_PATH_RE.search(d):
            raise DataplaneYamlBuildError(
                f"search_dirs entry {d!r} contains an absolute developer path "
                f"(/Users/, /home/*/, C:\\, or ..). Use OBSERVO_LUA_DIR env var or a "
                f"relative path the operator wires on deploy."
            )
    return list(search_dirs)


def _validate_lua_transform_keys(custom_keys: Dict[str, Any]) -> None:
    """Reject forbidden keys on v3 lua transforms (Phase 5.A safety net)."""
    forbidden = set(custom_keys.keys()) & _FORBIDDEN_V3_LUA_TRANSFORM_KEYS
    if forbidden:
        raise DataplaneYamlBuildError(
            f"forbidden keys on v3 lua transform: {sorted(forbidden)}. "
            f"These keys are rejected by the dataplane binary's lua deserializer "
            f"(see CLAUDE.md \"Standalone console wire format\" for the full list)."
        )


def build_lua_transform(
    transform_id: str,
    inputs: List[str],
    lua_body: str,
    *,
    parallelism: int = 1,
    search_dirs: Optional[List[str]] = None,
    process_fn: str = "process",
    version: Literal["2", "3"] = "3",
    extra_keys: Optional[Dict[str, Any]] = None,
) -> LuaTransform:
    """Construct a validated LuaTransform. All safety checks fire here.

    The caller supplies a lua_body that SHOULD already be wrapped via
    components.lua_deploy_wrapper.wrap_for_observo (Phase 2.A) - this builder
    does NOT re-wrap, and does NOT inline OCSF helpers.
    """
    if extra_keys:
        _validate_lua_transform_keys(extra_keys)
    sanitized = _sanitize_search_dirs(search_dirs or [])
    return LuaTransform(
        id=transform_id,
        inputs=inputs,
        source=lua_body,
        parallelism=parallelism,
        search_dirs=sanitized,
        process_fn=process_fn,
        version=version,
    )


def build_sentinelone_hec_sink(
    sink_id: str,
    inputs: List[str],
    endpoint: str,
    default_token: str,
) -> SplunkHecSink:
    """Construct the S1 HEC sink per plan 5.B.

    Modeled as type: splunk_hec_logs (there is no dedicated sentinelone sink type).
    default_token is the caller's responsibility - do not commit real tokens.
    """
    if not endpoint.startswith("https://"):
        raise DataplaneYamlBuildError(
            f"S1 HEC endpoint must be https (got {endpoint!r})"
        )
    return SplunkHecSink(
        id=sink_id,
        inputs=inputs,
        endpoint=endpoint,
        default_token=default_token,
    )


def build_pipeline_yaml(
    transforms: List[LuaTransform],
    sinks: List[SplunkHecSink],
    sources: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Assemble the top-level pipeline dict suitable for `yaml.safe_dump`.

    Returns a dict with keys: sources, transforms, sinks - the Vector YAML
    layout the dataplane binary expects. The caller is responsible for
    serializing via yaml.safe_dump (we don't couple to pyyaml here).
    """
    pipeline: Dict[str, Any] = {
        "sources": sources or {},
        "transforms": {t.id: t.to_yaml_dict() for t in transforms},
        "sinks": {s.id: s.to_yaml_dict() for s in sinks},
    }
    return pipeline
