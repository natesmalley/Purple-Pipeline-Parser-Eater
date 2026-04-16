"""Persistent settings store with env-var fallthrough.

On-disk layout: ``/app/data/settings/credentials.json`` on the shared
``app-data`` named volume.  The JSON shape mirrors the canonical schema
defined in the plan (``providers``, ``tuning``, ``integrations``, ``rag``).

Thread-safe via ``threading.RLock``.  Reads are mtime-cached with a
5-second re-stat throttle so hot paths don't hit disk on every call.
"""
from __future__ import annotations

import copy
import json
import logging
import os
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level singleton registry (FIX 4)
# ---------------------------------------------------------------------------
_global_instance: Optional["SettingsStore"] = None


def get_global_store() -> Optional["SettingsStore"]:
    """Return the globally registered SettingsStore, or None."""
    return _global_instance


def set_global_store(store: "SettingsStore") -> None:
    """Register *store* as the global singleton."""
    global _global_instance
    _global_instance = store


# ---------------------------------------------------------------------------
# Env-var fallthrough map
# ---------------------------------------------------------------------------
_ENV_FALLBACK: Dict[str, str] = {
    "providers.anthropic.api_key": "ANTHROPIC_API_KEY",
    "providers.anthropic.model": "ANTHROPIC_MODEL",
    "providers.anthropic.strong_model": "ANTHROPIC_STRONG_MODEL",
    "providers.openai.api_key": "OPENAI_API_KEY",
    "providers.openai.model": "OPENAI_MODEL",
    "providers.openai.strong_model": "OPENAI_STRONG_MODEL",
    "providers.gemini.api_key": "GEMINI_API_KEY",
    "providers.gemini.model": "GEMINI_MODEL",
    "providers.gemini.strong_model": "GEMINI_STRONG_MODEL",
    "providers.active": "LLM_PROVIDER_PREFERENCE",
    "tuning.llm_max_tokens": "LLM_MAX_TOKENS",
    "tuning.llm_max_iterations": "LLM_MAX_ITERATIONS",
    "tuning.workbench_max_sample_chars": "WORKBENCH_MAX_SAMPLE_CHARS",
    "tuning.workbench_max_total_sample_chars": "WORKBENCH_MAX_TOTAL_SAMPLE_CHARS",
    "integrations.github.token": "GITHUB_TOKEN",
    "integrations.github.owner": "GITHUB_OWNER",
    "integrations.github.repo": "GITHUB_REPO",
}

# Paths that resolve from runtime_config instead of env vars
_CONFIG_FALLBACK: Dict[str, tuple] = {
    "integrations.observo.api_key": ("observo", "api_key"),
    "integrations.observo.base_url": ("observo", "base_url"),
    "integrations.sdl.api_url": ("sentinelone_sdl", "api_url"),
    "integrations.sdl.api_key": ("sentinelone_sdl", "api_key"),
    "integrations.sdl.enabled": ("sentinelone_sdl", "audit_logging_enabled"),
    "integrations.sdl.batch_size": ("sentinelone_sdl", "batch_size"),
    "integrations.sdl.retry_attempts": ("sentinelone_sdl", "retry_attempts"),
    "rag.enabled": ("rag", "enabled"),
    "tuning.anthropic_temperature": ("anthropic", "temperature"),
}

# Secret-leaf paths (redacted in all_redacted output)
_SECRET_PATHS = frozenset({
    "providers.anthropic.api_key",
    "providers.openai.api_key",
    "providers.gemini.api_key",
    "integrations.github.token",
    "integrations.observo.api_key",
    "integrations.sdl.api_key",
})

# Default schema
_DEFAULTS: Dict[str, Any] = {
    "schema_version": 1,
    "providers": {
        "anthropic": {
            "api_key": None,
            "model": "claude-haiku-4-5-20251001",
            "strong_model": "claude-sonnet-4-6",
            "top_model": "claude-opus-4-6",
            "extended_thinking": True,
        },
        "openai": {
            "api_key": None,
            "model": "gpt-5.4-mini",
            "strong_model": "gpt-5.4",
            "top_model": "gpt-5.3-codex",
            "prefer_codex_for_code": False,
        },
        "gemini": {
            "api_key": None,
            "model": "gemini-3.1-flash-lite",
            "strong_model": "gemini-3-flash",
            "top_model": "gemini-3.1-pro",
            "prefer_reasoning_pro": True,
        },
        "active": "anthropic",
    },
    "tuning": {
        "llm_max_tokens": 3000,
        "llm_max_iterations": 2,
        "anthropic_temperature": 0.0,
        "workbench_max_sample_chars": 150000,
        "workbench_max_total_sample_chars": 1500000,
    },
    "integrations": {
        "github": {"token": None, "owner": "natesmalley", "repo": "ai-siem"},
        "observo": {"api_key": None, "base_url": "https://p01-api.observo.ai"},
        "sdl": {
            "api_url": None,
            "api_key": None,
            "enabled": False,
            "batch_size": 100,
            "retry_attempts": 3,
        },
    },
    "rag": {"enabled": True},
}

# Overlay mapping: store dotted path -> target config key path
_OVERLAY_MAP: Dict[str, tuple] = {
    "providers.anthropic.api_key": ("anthropic", "api_key"),
    "providers.anthropic.model": ("anthropic", "model"),
    "providers.anthropic.strong_model": ("anthropic", "strong_model"),
    "providers.openai.api_key": ("openai", "api_key"),
    "providers.openai.model": ("openai", "model"),
    "providers.openai.strong_model": ("openai", "strong_model"),
    "providers.gemini.api_key": ("gemini", "api_key"),
    "providers.gemini.model": ("gemini", "model"),
    "providers.gemini.strong_model": ("gemini", "strong_model"),
    "tuning.anthropic_temperature": ("anthropic", "temperature"),
    "integrations.github.token": ("github", "token"),
    "integrations.github.owner": ("github", "target_repo_owner"),
    "integrations.github.repo": ("github", "target_repo_name"),
    "integrations.observo.api_key": ("observo", "api_key"),
    "integrations.observo.base_url": ("observo", "base_url"),
    "integrations.sdl.api_url": ("sentinelone_sdl", "api_url"),
    "integrations.sdl.api_key": ("sentinelone_sdl", "api_key"),
    "integrations.sdl.enabled": ("sentinelone_sdl", "audit_logging_enabled"),
    "integrations.sdl.batch_size": ("sentinelone_sdl", "batch_size"),
    "integrations.sdl.retry_attempts": ("sentinelone_sdl", "retry_attempts"),
    "rag.enabled": ("rag", "enabled"),
}


class SettingsStore:
    """Persistent settings with env-var / config.yaml fallthrough.

    Parameters
    ----------
    runtime_config : dict
        Reference to the live ``self.config`` dict from the worker or web
        boot path.  ``update()`` calls ``apply_overlay(runtime_config)``
        as a side-effect so live-apply values flow immediately.
    path : str | Path
        On-disk JSON file (default ``data/settings/credentials.json``).
    """

    def __init__(
        self,
        runtime_config: Optional[Dict[str, Any]] = None,
        path: Optional[str] = None,
    ):
        self._lock = threading.RLock()
        self.runtime_config = runtime_config or {}
        self._path = Path(
            path or os.environ.get(
                "SETTINGS_STORE_PATH",
                "data/settings/credentials.json",
            )
        )
        self._cache: Optional[Dict[str, Any]] = None
        self._cache_mtime: float = 0.0
        self._last_stat: float = 0.0

    # ----- internal helpers -----

    def _load(self) -> Dict[str, Any]:
        """Load from disk with 5-second mtime cache."""
        now = time.monotonic()
        if self._cache is not None and (now - self._last_stat) < 5.0:
            return self._cache
        self._last_stat = now
        try:
            st = self._path.stat()
            disk_mtime = st.st_mtime
        except FileNotFoundError:
            self._cache = {}
            return self._cache
        if self._cache is not None and disk_mtime == self._cache_mtime:
            return self._cache
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._cache = data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            self._cache = {}
        self._cache_mtime = disk_mtime
        return self._cache

    def _write(self, data: Dict[str, Any]) -> None:
        """Atomic write via tempfile + os.replace."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        data.setdefault("schema_version", 1)
        fd, tmp = tempfile.mkstemp(
            dir=str(self._path.parent), suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, str(self._path))
            try:
                os.chmod(str(self._path), 0o600)
            except OSError:
                pass
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        self._cache = data
        try:
            self._cache_mtime = self._path.stat().st_mtime
        except OSError:
            self._cache_mtime = 0.0
        self._last_stat = time.monotonic()

    @staticmethod
    def _get_nested(d: dict, parts: list) -> Any:
        """Walk into a nested dict by key parts; return None on miss."""
        for p in parts:
            if not isinstance(d, dict):
                return None
            d = d.get(p)
        return d

    @staticmethod
    def _set_nested(d: dict, parts: list, value: Any) -> None:
        """Set a value in a nested dict, creating intermediaries."""
        for p in parts[:-1]:
            sub = d.get(p)
            if not isinstance(sub, dict):
                sub = {}
                d[p] = sub
            d = sub
        d[parts[-1]] = value

    # ----- public API -----

    def get(self, path: str, default: Any = None) -> Any:
        """Return the value at *path* (dotted), with fallthrough.

        Resolution order:
        1. On-disk store value (if set and not None)
        2. Env-var fallback (per ``_ENV_FALLBACK``)
        3. Config.yaml fallback (per ``_CONFIG_FALLBACK``)
        4. Schema default (per ``_DEFAULTS``)
        5. Caller-supplied *default*
        """
        parts = path.split(".")
        with self._lock:
            data = self._load()
            val = self._get_nested(data, parts)
        if val is not None:
            return val

        # Env-var fallthrough
        env_key = _ENV_FALLBACK.get(path)
        if env_key:
            env_val = os.environ.get(env_key)
            if env_val is not None:
                return env_val

        # Config.yaml fallthrough
        cfg_path = _CONFIG_FALLBACK.get(path)
        if cfg_path and self.runtime_config:
            cfg_val = self._get_nested(self.runtime_config, list(cfg_path))
            if cfg_val is not None:
                return cfg_val

        # Schema default
        schema_val = self._get_nested(_DEFAULTS, parts)
        if schema_val is not None:
            return schema_val

        return default

    def update(self, patch: Dict[str, Any]) -> Dict[str, Any]:
        """Merge *patch* into the store, write atomically, apply overlay.

        For secret fields: ``None`` clears, empty string leaves unchanged,
        non-empty string replaces.

        Returns the full (non-redacted) store contents after write.
        """
        with self._lock:
            data = copy.deepcopy(self._load())
            self._merge(data, patch)
            self._write(data)
            self.apply_overlay(self.runtime_config)
            return self.all_redacted()

    def _merge(self, target: dict, patch: dict, prefix: str = "") -> None:
        """Recursively merge *patch* into *target*."""
        for key, value in patch.items():
            dotted = "%s.%s" % (prefix, key) if prefix else key
            if isinstance(value, dict) and isinstance(target.get(key), dict):
                self._merge(target[key], value, dotted)
            elif dotted in _SECRET_PATHS and value == "":
                # Empty string = leave unchanged
                continue
            else:
                target[key] = value

    def apply_overlay(self, target_config: dict) -> None:
        """Write stored values into *target_config* at legacy key paths.

        Called at boot AND on every ``update()``.  Missing store sections
        are a no-op (the existing config.yaml values stand).
        """
        if target_config is None:
            return
        with self._lock:
            data = self._load()
        if not data:
            return
        for store_path, cfg_keys in _OVERLAY_MAP.items():
            parts = store_path.split(".")
            val = self._get_nested(data, parts)
            if val is None:
                continue
            # Ensure section exists
            section = cfg_keys[0]
            if section not in target_config:
                target_config[section] = {}
            if not isinstance(target_config[section], dict):
                target_config[section] = {}
            target_config[section][cfg_keys[1]] = val

    def all_redacted(self) -> Dict[str, Any]:
        """Return the full schema tree with secrets masked.

        Secrets become ``{"set": true, "last4": "wxyz"}`` or
        ``{"set": false}``.
        """
        with self._lock:
            data = self._load()
        # Start from defaults, overlay stored values
        result = copy.deepcopy(_DEFAULTS)
        self._deep_update(result, copy.deepcopy(data))
        # Inject env-var fallthrough for unset paths
        for dotted, env_key in _ENV_FALLBACK.items():
            parts = dotted.split(".")
            current = self._get_nested(result, parts)
            if current is None:
                env_val = os.environ.get(env_key)
                if env_val is not None:
                    self._set_nested(result, parts, env_val)
        # Config fallthrough for unset paths
        for dotted, cfg_keys in _CONFIG_FALLBACK.items():
            parts = dotted.split(".")
            current = self._get_nested(result, parts)
            if current is None and self.runtime_config:
                cfg_val = self._get_nested(self.runtime_config, list(cfg_keys))
                if cfg_val is not None:
                    self._set_nested(result, parts, cfg_val)
        # Redact secrets
        for secret_path in _SECRET_PATHS:
            parts = secret_path.split(".")
            raw = self._get_nested(result, parts)
            if raw and isinstance(raw, str) and len(raw) > 0:
                self._set_nested(result, parts, {
                    "set": True,
                    "last4": raw[-4:],
                })
            else:
                self._set_nested(result, parts, {"set": False})
        # Strip updated_at and schema_version noise
        result.pop("updated_at", None)
        result.setdefault("schema_version", 1)
        return result

    def mtime(self) -> float:
        """Return the on-disk mtime (for cache-bust comparisons)."""
        with self._lock:
            self._load()  # refresh cache
            return self._cache_mtime

    @staticmethod
    def _deep_update(base: dict, overlay: dict) -> None:
        for k, v in overlay.items():
            if isinstance(v, dict) and isinstance(base.get(k), dict):
                SettingsStore._deep_update(base[k], v)
            else:
                base[k] = v
