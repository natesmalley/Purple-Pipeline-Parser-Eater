"""Tests for components.settings_store.SettingsStore."""
from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from unittest import mock

import pytest

from components.settings_store import SettingsStore


@pytest.fixture()
def tmp_store(tmp_path):
    """Return a SettingsStore backed by a temp file."""
    path = tmp_path / "settings" / "credentials.json"
    return SettingsStore(runtime_config={}, path=str(path))


# ------------------------------------------------------------------
# get() with dotted paths
# ------------------------------------------------------------------

class TestGet:
    def test_returns_default_when_file_missing(self, tmp_store):
        assert tmp_store.get("providers.active") == "anthropic"

    def test_returns_schema_default_for_known_path(self, tmp_store):
        assert tmp_store.get("tuning.llm_max_tokens") == 3000

    def test_returns_caller_default_for_unknown_path(self, tmp_store):
        assert tmp_store.get("nonexistent.path", "fallback") == "fallback"

    def test_returns_stored_value_over_default(self, tmp_store):
        tmp_store.update({"providers": {"active": "openai"}})
        assert tmp_store.get("providers.active") == "openai"

    def test_nested_dotted_path(self, tmp_store):
        tmp_store.update({
            "integrations": {"github": {"owner": "testorg"}}
        })
        assert tmp_store.get("integrations.github.owner") == "testorg"


# ------------------------------------------------------------------
# Env-var fallthrough
# ------------------------------------------------------------------

class TestEnvFallthrough:
    def test_env_var_used_when_store_unset(self, tmp_store):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
            val = tmp_store.get("providers.anthropic.api_key")
            assert val == "sk-test"

    def test_store_value_beats_env_var(self, tmp_store):
        tmp_store.update({
            "providers": {"anthropic": {"api_key": "sk-stored"}}
        })
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-env"}):
            val = tmp_store.get("providers.anthropic.api_key")
            assert val == "sk-stored"


# ------------------------------------------------------------------
# update() — atomic write + readback
# ------------------------------------------------------------------

class TestUpdate:
    def test_roundtrip(self, tmp_store):
        tmp_store.update({"tuning": {"llm_max_tokens": 4000}})
        assert tmp_store.get("tuning.llm_max_tokens") == 4000

    def test_file_written(self, tmp_store):
        tmp_store.update({"providers": {"active": "gemini"}})
        raw = json.loads(tmp_store._path.read_text(encoding="utf-8"))
        assert raw["providers"]["active"] == "gemini"

    def test_null_clears_secret(self, tmp_store):
        tmp_store.update({
            "providers": {"anthropic": {"api_key": "sk-secret"}}
        })
        assert tmp_store.get("providers.anthropic.api_key") == "sk-secret"
        tmp_store.update({
            "providers": {"anthropic": {"api_key": None}}
        })
        # None stored means fallthrough to env/default
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ANTHROPIC_API_KEY", None)
            val = tmp_store.get("providers.anthropic.api_key")
            assert val is None

    def test_empty_string_leaves_secret_unchanged(self, tmp_store):
        tmp_store.update({
            "providers": {"anthropic": {"api_key": "sk-original"}}
        })
        tmp_store.update({
            "providers": {"anthropic": {"api_key": ""}}
        })
        assert tmp_store.get("providers.anthropic.api_key") == "sk-original"

    def test_updated_at_set(self, tmp_store):
        tmp_store.update({"tuning": {"llm_max_tokens": 5000}})
        raw = json.loads(tmp_store._path.read_text(encoding="utf-8"))
        assert "updated_at" in raw


# ------------------------------------------------------------------
# apply_overlay()
# ------------------------------------------------------------------

class TestApplyOverlay:
    def test_writes_into_target_config(self, tmp_store):
        tmp_store.update({
            "providers": {"anthropic": {"api_key": "sk-overlay"}},
            "integrations": {"github": {"owner": "myorg"}},
        })
        target = {}
        tmp_store.apply_overlay(target)
        assert target["anthropic"]["api_key"] == "sk-overlay"
        assert target["github"]["target_repo_owner"] == "myorg"

    def test_github_owner_maps_to_target_repo_owner(self, tmp_store):
        tmp_store.update({
            "integrations": {"github": {"owner": "acme"}}
        })
        target = {}
        tmp_store.apply_overlay(target)
        assert target["github"]["target_repo_owner"] == "acme"

    def test_sdl_maps_to_sentinelone_sdl(self, tmp_store):
        tmp_store.update({
            "integrations": {
                "sdl": {
                    "api_url": "https://sdl.example.com",
                    "enabled": True,
                }
            }
        })
        target = {}
        tmp_store.apply_overlay(target)
        assert target["sentinelone_sdl"]["api_url"] == "https://sdl.example.com"
        assert target["sentinelone_sdl"]["audit_logging_enabled"] is True

    def test_temperature_maps_to_anthropic_temperature(self, tmp_store):
        tmp_store.update({"tuning": {"anthropic_temperature": 0.5}})
        target = {}
        tmp_store.apply_overlay(target)
        assert target["anthropic"]["temperature"] == 0.5

    def test_noop_when_store_empty(self, tmp_store):
        target = {"existing": "value"}
        tmp_store.apply_overlay(target)
        assert target == {"existing": "value"}

    def test_noop_when_target_empty_dict(self, tmp_store):
        # Should not crash on empty target
        tmp_store.apply_overlay({})


# ------------------------------------------------------------------
# all_redacted()
# ------------------------------------------------------------------

class TestAllRedacted:
    def test_masks_secrets(self, tmp_store):
        tmp_store.update({
            "providers": {"anthropic": {"api_key": "sk-ant-abcdefgh"}}
        })
        redacted = tmp_store.all_redacted()
        key_info = redacted["providers"]["anthropic"]["api_key"]
        assert key_info["set"] is True
        assert key_info["last4"] == "efgh"

    def test_unset_secret_shows_set_false(self, tmp_store):
        redacted = tmp_store.all_redacted()
        key_info = redacted["providers"]["openai"]["api_key"]
        assert key_info["set"] is False

    def test_non_secret_fields_not_masked(self, tmp_store):
        tmp_store.update({"providers": {"active": "gemini"}})
        redacted = tmp_store.all_redacted()
        assert redacted["providers"]["active"] == "gemini"

    def test_includes_schema_defaults(self, tmp_store):
        redacted = tmp_store.all_redacted()
        assert redacted["tuning"]["llm_max_tokens"] == 3000
        assert redacted["schema_version"] == 1


# ------------------------------------------------------------------
# mtime()
# ------------------------------------------------------------------

class TestMtime:
    def test_changes_after_update(self, tmp_store):
        m1 = tmp_store.mtime()
        # Force a slight delay so mtime differs
        time.sleep(0.05)
        tmp_store.update({"tuning": {"llm_max_tokens": 9999}})
        m2 = tmp_store.mtime()
        assert m2 >= m1
        # If file didn't exist before, m1 is 0
        if m1 == 0.0:
            assert m2 > 0

    def test_mtime_zero_when_no_file(self, tmp_store):
        assert tmp_store.mtime() == 0.0


# ------------------------------------------------------------------
# providers.active validation (integration with routes)
# ------------------------------------------------------------------

class TestActiveValidation:
    def test_update_accepts_valid_active(self, tmp_store):
        for name in ("anthropic", "openai", "gemini"):
            tmp_store.update({"providers": {"active": name}})
            assert tmp_store.get("providers.active") == name
