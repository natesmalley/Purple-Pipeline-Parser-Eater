"""
Observo.ai API Client - Backward Compatibility Wrapper

Targets the SaaS REST control plane at p01-api.observo.ai/gateway/v1/*.
Do NOT mutate to snake_case based on dataplane-binary findings (plan
Phase 4.C).

DEPRECATED: This file previously imported from a non-existent
`components.observo` package. Those symbols (`ObservoAPI`,
`ObservoConnectionError`, `ObservoAuthenticationError`,
`ObservoValidationError`) are not defined anywhere in the current
codebase. For new code, use `components.observo_client.ObservoAPIClient`
or, for the error type, `utils.error_handler.ObservoAPIError`.

Phase 0 fix: the previous `from .observo import (...)` line raised
`ModuleNotFoundError` at import time, blocking every caller that touched
this module. To keep the import surface alive without reviving dead code,
the missing symbols are re-exported as TODO stubs here. Real wiring to
the SaaS client happens in Phase 4.
"""

# TODO: wire during Phase 4 — re-export from the real location once the
# observo client package separation lands. `utils.error_handler` pulls
# `tenacity`, which is not in `requirements-test.txt`, so we cannot import
# from there at Phase 0 without breaking the minimal-venv import smoke
# gate. Define a local stub base class instead.
class ObservoAPIError(Exception):  # TODO: wire during Phase 4
    """Stub placeholder for `ObservoAPIError`.

    The real class lives at `utils.error_handler.ObservoAPIError` but
    pulling it in would require `tenacity` in the Phase 0 minimal venv.
    """


class ObservoAPI:  # TODO: wire during Phase 4
    """Stub placeholder for the missing `ObservoAPI` symbol.

    The legacy `components.observo` package this wrapper pointed at does
    not exist in the current tree. Phase 4 (SaaS reconciliation) is the
    phase that decides the real shape. Instantiating this stub raises so
    callers fail loudly rather than silently no-op.
    """

    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            "ObservoAPI is a Phase 0 stub; real client lands in Phase 4. "
            "Use components.observo_client.ObservoAPIClient in the meantime."
        )


class ObservoConnectionError(ObservoAPIError):  # TODO: wire during Phase 4
    """Stub placeholder for the missing `ObservoConnectionError` symbol."""


class ObservoAuthenticationError(ObservoAPIError):  # TODO: wire during Phase 4
    """Stub placeholder for the missing `ObservoAuthenticationError` symbol."""


class ObservoValidationError(ObservoAPIError):  # TODO: wire during Phase 4
    """Stub placeholder for the missing `ObservoValidationError` symbol."""


__all__ = [
    'ObservoAPI',
    'ObservoAPIError',
    'ObservoConnectionError',
    'ObservoAuthenticationError',
    'ObservoValidationError'
]
