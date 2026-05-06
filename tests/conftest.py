"""Project-wide pytest fixtures.

FU17: globally redirect ``COST_LEDGER_PATH`` to a per-test tmp_path so
that any test exercising ``LuaGenerator._invoke_provider`` (directly or
transitively) cannot leak rows into the production default at
``data/runtime/cost_ledger.jsonl``. The cost-ledger module's singleton
lazily reads the env var on first ``get_default_ledger()`` call, so we
also reset the singleton inside the fixture to make the env override
effective for every test.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolate_cost_ledger_globally(monkeypatch, tmp_path):
    """Autouse fixture — applied to every test in the suite.

    Routes ``COST_LEDGER_PATH`` to ``<tmp_path>/cost_ledger.jsonl`` and
    clears the module singleton so the next ``get_default_ledger()``
    call re-resolves env. The cost_ledger module may not be importable
    in some lightweight test contexts (e.g. tests that stub out
    ``components`` entirely), so the import is guarded.
    """
    monkeypatch.setenv("COST_LEDGER_PATH", str(tmp_path / "cost_ledger.jsonl"))
    try:
        from components.cost_ledger import set_default_ledger
        set_default_ledger(None)
    except ImportError:
        # cost_ledger module not available in this test environment —
        # the env var still takes effect if/when it's later imported.
        pass
    yield
    # Post-test reset so a leftover singleton from this test can't
    # bleed into the next one before its monkeypatch lands.
    try:
        from components.cost_ledger import set_default_ledger
        set_default_ledger(None)
    except ImportError:
        pass
