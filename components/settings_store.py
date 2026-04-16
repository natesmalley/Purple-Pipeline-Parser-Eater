"""Persistent operator-settings store backed by a JSON file on the shared app-data volume.

Canonical schema: see the plan file at .claude/plans/lovely-hugging-mango.md for the
full tree shape and the env-var fallback map.

Two integration strategies:
  Strategy A — live-apply sites call ``SettingsStore.get("providers.anthropic.api_key")``
               directly, replacing ``os.environ.get("ANTHROPIC_API_KEY")``.
  Strategy B — restart-required singletons read ``self.config[...]`` at __init__ time
               and never touch SettingsStore directly.  Instead, ``apply_overlay(config)``
               is called at boot (and on every ``update()``) to write store values into
               the runtime config dict at the legacy key paths those constructors already
               read.  Zero constructor changes required.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_DEFAULT_STORE_PATH = "/app/data/settings/credentials.json"

_ENV_FALLBACK_MAP: Dict[str, str] = {
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

_CONFIG_FALLBACK_MAP: Dict[str, tuple] = {
    "tuning.anthropic_temperature": ("anthropic", "temperature"),
    "integrations.observo.api_key": ("observo", "api_key"),
    "integrations.observo.base_url": ("observo", "base_url"),
    "integrations.sdl.api_url": ("sentinelone_sdl", "api_url"),
    "integrations.sdl.api_key": ("sentinelone_sdl", "api_key"),
    "integrations.sdl.enabled": ("sentinelone_sdl", "audit_logging_enabled"),
    "integrations.sdl.batch_size": ("sentinelone_sdl", "batch_size"),
    "integrations.sdl.retry_attempts": ("sentinelone_sdl", "retry_attempts"),
    "rag.enabled": ("rag", "enabled"),
}

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
    "providers.active": ("llm", "provider_preference"),
    "tuning.anthropic_temperature": ("anthropic", "temperature"),
    "tuning.llm_max_tokens": ("llm", "max_tokens"),
    "tuning.llm_max_iterations": ("llm", "max_iterations"),
    "tuning.workbench_max_sample_chars": ("workbench", "max_sample_chars"),
    "tuning.workbench_max_total_sample_chars": ("workbench", "max_total_sample_chars"),
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

_SECRET_PATTERNS = ("api_key", "token", "secret", "password")

_MTIME_CACHE_TTL = 5.0


def _is_secret_key(key: str) -> bool:
    return any(p in key for p in _SECRET_PATTERNS)


def _redact(value: Any, key: str) -> Any:
    if not _is_secret_key(key) or value is None:
        return value
    s = str(value)
    if len(s) < 4:
        return {"set": bool(s), "last4": ""}
    return {"set": True, "last4": s[-4:]}


def _deep_get(data: dict, dotted: str, default: Any = None) -> Any:
    parts = dotted.split(".")
    node = data
    for part in parts:
        if not isinstance(node, dict):
            return default
        node = node.get(part)
        if node is None:
            return default
    return node


def _deep_set(data: dict, dotted: str, value: Any) -> None:
    parts = dotted.split(".")
    node = data
    for part in parts[:-1]:
        if part not in node or not isinstance(node[part], dict):
            node[part] = {}
        node = node[part]
    node[parts[-1]] = value


def _deep_merge(base: dict, patch: dict) -> dict:
    merged = dict(base)
    for key, val in patch.items():
        if isinstance(val, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], val)
        elif val == "":
            pass
        else:
            merged[key] = val
    return merged


class SettingsStore:
    """Thread-safe, mtime-cached JSON settings store with env-var fallthrough
    and a startup overlay contract for restart-required singletons.
    """

    def __init__(
        self,
        runtime_config: Optional[Dict] = None,
        store_path: Optional[str] = None,
    ):
        self._path = Path(store_path or os.environ.get("SETTINGS_STORE_PATH", _DEFAULT_STORE_PATH))
        self._runtime_config = runtime_config or {}
        self._lock = threading.RLock()
        self._data: Dict = {}
        self._file_mtime: float = 0.0
        self._last_stat: float = 0.0
        self._load()

    def _load(self) -> None:
        with self._lock:
            if not self._path.exists():
                self._data = {}
                self._file_mtime = 0.0
                return
            try:
                raw = self._path.read_text(encoding="utf-8")
                self._data = json.loads(raw) if raw.strip() else {}
                self._file_mtime = self._path.stat().st_mtime
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("SettingsStore: failed to load %s: %s", self._path, exc)
                self._data = {}
                self._file_mtime = 0.0

    def _maybe_reload(self) -> None:
        now = time.monotonic()
        if now - self._last_stat < _MTIME_CACHE_TTL:
            return
        self._last_stat = now
        try:
            if self._path.exists():
                mt = self._path.stat().st_mtime
                if mt > self._file_mtime:
                    self._load()
        except OSError:
            pass

    def mtime(self) -> float:
        self._maybe_reload()
        return self._file_mtime

    def get(self, path: str, default: Any = None) -> Any:
        self._maybe_reload()
        with self._lock:
            val = _deep_get(self._data, path)
            if val is not None:
                return val

        env_key = _ENV_FALLBACK_MAP.get(path)
        if env_key:
            env_val = os.environ.get(env_key)
            if env_val is not None:
                if isinstance(default, (int, float)):
                    try:
                        return type(default)(env_val)
                    except (ValueError, TypeError):
                        pass
                return env_val

        cfg_path = _CONFIG_FALLBACK_MAP.get(path)
        if cfg_path and self._runtime_config:
            section, key = cfg_path
            section_dict = self._runtime_config.get(section, {})
            if isinstance(section_dict, dict):
                cfg_val = section_dict.get(key)
                if cfg_val is not None:
                    return cfg_val

        return default

    def update(self, patch: dict) -> dict:
        with self._lock:
            self._maybe_reload()
            self._data = _deep_merge(self._data, patch)
            self._data["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            self._data.setdefault("schema_version", 1)
            self._write()
            self.apply_overlay(self._runtime_config)
            return self.all_redacted()

    def _write(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd = None
        tmp_path = None
        try:
            fd_int, tmp_path = tempfile.mkstemp(
                dir=str(self._path.parent),
                prefix=".settings-",
                suffix=".tmp",
            )
            fd = os.fdopen(fd_int, "w", encoding="utf-8")
            json.dump(self._data, fd, indent=2, sort_keys=True, default=str)
            fd.flush()
            os.fsync(fd.fileno())
            fd.close()
            fd = None
            os.replace(tmp_path, str(self._path))
            self._file_mtime = self._path.stat().st_mtime
            tmp_path = None
        except OSError as exc:
            logger.error("SettingsStore: failed to write %s: %s", self._path, exc)
            raise
        finally:
            if fd is not None:
                try:
                    fd.close()
                except OSError:
                    pass
            if tmp_path is not None:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    def apply_overlay(self, target_config: dict) -> None:
        if not target_config:
            return
        self._maybe_reload()
        with self._lock:
            for store_path, (section, key) in _OVERLAY_MAP.items():
                val = _deep_get(self._data, store_path)
                if val is None:
                    continue
                if section not in target_config:
                    target_config[section] = {}
                if not isinstance(target_config[section], dict):
                    target_config[section] = {}
                target_config[section][key] = val

    def all_redacted(self) -> dict:
        self._maybe_reload()
        with self._lock:
            return self._redact_tree(dict(self._data))

    def _redact_tree(self, node: Any, parent_key: str = "") -> Any:
        if isinstance(node, dict):
            return {
                k: self._redact_tree(v, k)
                for k, v in node.items()
            }
        if isinstance(node, list):
            return [self._redact_tree(v, parent_key) for v in node]
        if _is_secret_key(parent_key) and node is not None:
            return _redact(node, parent_key)
        return node

    def raw(self) -> dict:
        self._maybe_reload()
        with self._lock:
            return dict(self._data)
