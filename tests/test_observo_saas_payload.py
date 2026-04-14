"""Phase 4.D -- SaaS payload shape regression gate.

Asserts that build_pipeline_json + the HTTP marshalling layer produce
exactly the shape captured in tests/fixtures/saas_cassettes/*.json.

This is the primary regression gate for Phase 4. Any future commit that
drifts the SaaS payload shape must either update the cassette (with a
commit message justifying the drift) or it fails this test.
"""
from __future__ import annotations

import asyncio
import json
import sys
import types
from pathlib import Path

# -- aiohttp stub ---------------------------------------------------------
# observo_client.py imports aiohttp at module top-level. The CI venv does
# not ship aiohttp (it's runtime-only). Install a minimal stub before the
# import so the SaaS payload tests can load components.observo_client.
if "aiohttp" not in sys.modules:
    _stub = types.ModuleType("aiohttp")

    class _StubTCPConnector:  # noqa: D401
        def __init__(self, *a, **kw):
            pass

    class _StubClientSession:
        def __init__(self, *a, **kw):
            pass

        async def close(self):
            return None

    class _StubClientError(Exception):
        pass

    _stub.TCPConnector = _StubTCPConnector
    _stub.ClientSession = _StubClientSession
    _stub.ClientError = _StubClientError
    sys.modules["aiohttp"] = _stub

if "anthropic" not in sys.modules:
    _astub = types.ModuleType("anthropic")

    class _StubAsyncAnthropic:
        def __init__(self, *a, **kw):
            pass

    _astub.AsyncAnthropic = _StubAsyncAnthropic
    sys.modules["anthropic"] = _astub

if "tenacity" not in sys.modules:
    _tstub = types.ModuleType("tenacity")

    def _noop_retry(*a, **kw):
        def _deco(f):
            return f
        return _deco

    _tstub.retry = _noop_retry
    _tstub.stop_after_attempt = lambda *a, **kw: None
    _tstub.wait_exponential = lambda *a, **kw: None
    _tstub.retry_if_exception_type = lambda *a, **kw: None
    sys.modules["tenacity"] = _tstub

# components.observo_client does `from .observo import ObservoAPI` which is
# a dead import path (there is no `components/observo/` package -- the real
# class lives in `components.observo_api_client`). In mock_mode the
# attribute is never used, but the import still fires. Stub it.
if "components.observo" not in sys.modules:
    _ostub = types.ModuleType("components.observo")

    class _StubObservoAPI:
        def __init__(self, *a, **kw):
            pass

    _ostub.ObservoAPI = _StubObservoAPI
    sys.modules["components.observo"] = _ostub
# -------------------------------------------------------------------------


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "saas_cassettes"


def _load_cassette(name: str) -> dict:
    return json.loads((FIXTURES_DIR / f"{name}.json").read_text(encoding="utf-8"))


def _make_client():
    """Instantiate ObservoAPIClient in mock mode (no network)."""
    from components.observo_client import ObservoAPIClient

    cfg = {"observo": {"api_key": "dry-run-mode", "site_id": 1}}
    return ObservoAPIClient(cfg)


def _sample_parser_analysis() -> dict:
    return {
        "parser_id": "example_parser",
        "ocsf_classification": {
            "class_uid": 2004,
            "class_name": "Detection Finding",
            "category_uid": 2,
            "category_name": "Findings",
        },
        "parser_complexity": {"level": "Medium"},
        "performance_characteristics": {"expected_volume": "Medium"},
    }


def _sample_lua() -> str:
    return "function processEvent(event)\n  return event\nend"


def _build_pipeline_json() -> dict:
    client = _make_client()
    return asyncio.run(
        client.build_pipeline_json(
            parser_analysis=_sample_parser_analysis(),
            lua_code=_sample_lua(),
            complete_metadata={"description": "example"},
        )
    )


# -------------------------------------------------------------------------
# Transform / Lua script config block
# -------------------------------------------------------------------------


class TestTransformLuaScriptPayload:
    def test_cassette_loads(self):
        cassette = _load_cassette("transform_lua_script")
        assert cassette["_endpoint"] == "POST /gateway/v1/transform"
        assert "transform" in cassette["request"]

    def test_config_block_uses_luaScript_camelCase(self):
        """The SaaS config block must use camelCase `luaScript`, NOT `lua_code`."""
        cassette = _load_cassette("transform_lua_script")
        cfg = cassette["request"]["transform"]["config"]
        assert "luaScript" in cfg
        assert "metricEvent" in cfg
        assert "bypassTransform" in cfg
        # Negative: snake_case variants must not leak into the SaaS cassette
        assert "lua_code" not in cfg
        assert "lua_script" not in cfg
        assert "metric_event" not in cfg
        assert "bypass_transform" not in cfg

    def test_build_pipeline_json_emits_luaScript_at_transform_level(self):
        """
        After Phase 4.C reconcile, the transform blob emitted by
        build_pipeline_json must carry a `config` dict whose keys match
        the cassette's config keys set.
        """
        from components.observo_client import ObservoAPIClient  # noqa: F401

        pipeline_json = _build_pipeline_json()
        assert pipeline_json["siteId"] == 1
        assert isinstance(pipeline_json["transforms"], list)
        assert len(pipeline_json["transforms"]) >= 1

        transform = pipeline_json["transforms"][0]
        # After the fix, the transform must carry a `config` block that matches
        # the cassette's config keys.
        assert "config" in transform, (
            f"Transform missing `config` block: {transform!r}"
        )
        cfg_keys = set(transform["config"].keys())

        cassette = _load_cassette("transform_lua_script")
        expected_cfg_keys = set(cassette["request"]["transform"]["config"].keys())
        assert expected_cfg_keys.issubset(cfg_keys), (
            f"Transform config keys {cfg_keys} missing required "
            f"cassette keys {expected_cfg_keys - cfg_keys}"
        )

        # The Lua body must be present under the camelCase key.
        assert "luaScript" in transform["config"]
        assert transform["config"]["luaScript"] == _sample_lua()

    def test_build_pipeline_json_does_not_leak_lua_code_to_http_layer(self):
        """
        `lua_code` is the internal Python-side name; it must not appear inside
        the `config` block that is destined for the SaaS HTTP POST.
        """
        pipeline_json = _build_pipeline_json()
        transform = pipeline_json["transforms"][0]
        assert "lua_code" not in transform.get("config", {})


# -------------------------------------------------------------------------
# Pipeline deserialize / action cassette loading sanity
# -------------------------------------------------------------------------


class TestPipelineCassetteSanity:
    def test_deserialize_cassette_loads(self):
        cassette = _load_cassette("pipeline_deserialize")
        assert cassette["_endpoint"] == "POST /gateway/v1/deserialize-pipeline"

    def test_action_cassette_loads(self):
        cassette = _load_cassette("pipeline_action")
        assert cassette["_endpoint"] == "PATCH /gateway/v1/pipeline/action"
        assert cassette["request"]["action"] == "DEPLOY"
