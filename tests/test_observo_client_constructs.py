"""W1 regression test: ObservoAPIClient must construct without the legacy
`_observo_deps()` lazy import.

Pre-W1, `ObservoAPIClient.__init__` called `_observo_deps()` which tried
to `from .observo import ObservoAPI` -- but `components/observo.py`
does not exist (it's a stubbed Phase-4 milestone), so any direct
construction raised `ModuleNotFoundError: No module named
'components.observo'` unless the test pre-stubbed `sys.modules`.

The audit showed the three names assigned from `_observo_deps()`
(`self.api_client`, `self.pipeline_builder`, `self.pipeline_optimizer`)
are never read anywhere in `components/`, `services/`, or
`orchestrator/`. W1 deletes the lazy import + the three assignments;
this test pins that direct construction works without the stub.
"""
from __future__ import annotations

import sys
import types


# Match the lazy-import shielding the other observo tests use, so this
# module is importable in minimal venvs that lack aiohttp / anthropic /
# tenacity. We do NOT stub `components.observo` -- the whole point of
# W1 is that no such stub should be necessary.
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


def test_observo_api_client_constructs_in_mock_mode():
    """Direct construction with `dry-run-mode` must not raise.

    Pre-W1: `ModuleNotFoundError: No module named 'components.observo'`
    Post-W1: clean construction, mock_mode=True.
    """
    from components.observo_client import ObservoAPIClient

    client = ObservoAPIClient({"observo": {"api_key": "dry-run-mode"}})

    assert client.mock_mode is True
    assert client.api_key == "dry-run-mode"
    # Default base_url + a Bearer-less header set when mock_mode is on.
    assert client.base_url == "https://p01-api.observo.ai"
    assert "Authorization" not in client.headers


def test_observo_api_client_constructs_with_real_key():
    """Non-mock-mode construction must also work post-W1.

    Pre-W1 this branch hit the same `_observo_deps()` ModuleNotFoundError
    AND tried to instantiate the missing `ObservoAPI` class. Post-W1 it
    just sets headers + delegates HTTP work to `_deploy_pipeline`.
    """
    from components.observo_client import ObservoAPIClient

    fake_key = "sk-fake-real-key-shape"
    client = ObservoAPIClient({"observo": {"api_key": fake_key}})

    assert client.mock_mode is False
    assert client.headers.get("Authorization") == f"Bearer {fake_key}"


def test_deploy_pipeline_method_remains_callable():
    """Positive control: the live SaaS deploy entrypoint is still bound.

    The W1 audit named `_deploy_pipeline` as the actual aiohttp path
    (now wrapped by the W5 SSRF gate). Make sure the deletion did not
    accidentally also remove that method.
    """
    from components.observo_client import ObservoAPIClient

    client = ObservoAPIClient({"observo": {"api_key": "dry-run-mode"}})
    assert callable(getattr(client, "_deploy_pipeline", None))
    assert callable(getattr(client, "deploy_validated_pipeline", None))


def test_no_residual_observo_deps_lazy_import_path():
    """The deleted `_observo_deps()` helper must not be re-resurrected.

    Pin the deletion at the symbol level so a future refactor that
    re-introduces a `components.observo` dependency triggers an
    immediate test failure instead of a silent ModuleNotFoundError at
    construction time.
    """
    import components.observo_client as oc

    assert not hasattr(oc, "_observo_deps"), (
        "_observo_deps() was deleted by W1 because the three names it "
        "returned (ObservoAPI / PipelineBuilder / PipelineOptimizer) "
        "were assignment-only. Re-introducing it without first "
        "implementing components.observo will crash construction."
    )
