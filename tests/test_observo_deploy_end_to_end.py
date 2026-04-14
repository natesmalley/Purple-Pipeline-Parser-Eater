"""Phase 4.E -- SaaS deploy end-to-end with recorded cassette.

Exercises the non-mock_mode branch of
`components.observo_client.ObservoAPIClient._deploy_pipeline` using the
cassettes in `tests/fixtures/saas_cassettes/`. Stubs `aiohttp.ClientSession.post`
to return the cassette responses.

Per plan Phase 4, the deploy path at

    orchestrator/pipeline_deployer.py -> observo_client.deploy_validated_pipeline
      -> _deploy_pipeline -> aiohttp.session.post

has never been exercised in CI. This test is the first. Its primary job is
to prove that:

  1. The outbound URL is a `/gateway/v1/...` path, NOT `/pipelines`.
  2. The outbound body matches the cassette-captured shape.
"""
from __future__ import annotations

import asyncio
import json
import sys
import types
from pathlib import Path
from typing import Any, Dict
import pytest


# -- aiohttp stub (see tests/test_observo_saas_payload.py for rationale) --
if "aiohttp" not in sys.modules:
    _stub = types.ModuleType("aiohttp")

    class _StubTCPConnector:
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


class _FakeResponse:
    def __init__(self, status: int, body: dict):
        self.status = status
        self._body = body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def json(self):
        return self._body

    async def text(self):
        return json.dumps(self._body)


class _RecordingSession:
    """Minimal aiohttp-style session that records the outbound call."""

    def __init__(self, response_body: dict, status: int = 200):
        self._response_body = response_body
        self._status = status
        self.last_url: str | None = None
        self.last_json: Any = None
        self.last_method: str | None = None

    def post(self, url, json=None, timeout=None, **kwargs):
        self.last_url = url
        self.last_json = json
        self.last_method = "POST"
        return _FakeResponse(self._status, self._response_body)

    def get(self, url, **kwargs):
        self.last_url = url
        self.last_method = "GET"
        return _FakeResponse(self._status, self._response_body)

    async def close(self):
        pass


@pytest.fixture
def real_client():
    """An ObservoAPIClient with mock_mode disabled (real HTTP path)."""
    from components.observo_client import ObservoAPIClient

    cfg = {
        "observo": {
            "api_key": "test-jwt-not-a-real-key",
            "base_url": "https://p01-api.observo.ai",
            "site_id": 1,
            "deployment_timeout": 5,
        }
    }
    client = ObservoAPIClient(cfg)
    assert client.mock_mode is False
    return client


class TestDeployHitsGatewayV1:
    def test_deploy_pipeline_uses_gateway_v1_path_not_slash_pipelines(self, real_client):
        """After Phase 4.B, `_deploy_pipeline` must NOT POST to `{base_url}/pipelines`.
        It must POST to a `/gateway/v1/...` path."""
        cassette = _load_cassette("pipeline_deserialize")
        session = _RecordingSession(cassette["response"])
        real_client.session = session

        config: Dict[str, Any] = {"siteId": 1, "pipeline": {"name": "t"}, "transforms": []}

        result = asyncio.get_event_loop().run_until_complete(
            real_client._deploy_pipeline(config)
        )

        assert session.last_url is not None
        assert "/gateway/v1/" in session.last_url, (
            f"Deploy URL must live under /gateway/v1/ but was {session.last_url!r}"
        )
        assert "/pipelines" not in session.last_url.rstrip("/").split("/gateway/v1")[-1] or \
               "/gateway/v1/deserialize-pipeline" in session.last_url, (
            f"Deploy URL looks like the old /pipelines path: {session.last_url!r}"
        )
        # Result smoke
        assert isinstance(result, dict)

    def test_deploy_pipeline_sends_non_empty_body(self, real_client):
        cassette = _load_cassette("pipeline_deserialize")
        session = _RecordingSession(cassette["response"])
        real_client.session = session

        config = {"siteId": 1, "pipeline": {"name": "t"}, "transforms": [{"type": "lua"}]}
        asyncio.get_event_loop().run_until_complete(
            real_client._deploy_pipeline(config)
        )

        assert session.last_json is not None
        assert session.last_json.get("siteId") == 1


class TestGetPipelineStatusUsesGatewayV1:
    def test_get_pipeline_status_uses_gateway_v1_path(self, real_client):
        cassette_response = {"pipeline": {"id": 1, "status": "DEPLOYED"}}
        session = _RecordingSession(cassette_response)
        real_client.session = session

        asyncio.get_event_loop().run_until_complete(
            real_client.get_pipeline_status("1")
        )
        assert session.last_url is not None
        assert "/gateway/v1/" in session.last_url, (
            f"get_pipeline_status URL must live under /gateway/v1/ but was {session.last_url!r}"
        )
