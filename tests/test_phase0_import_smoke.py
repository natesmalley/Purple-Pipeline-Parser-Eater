"""Phase 0 import-smoke tests.

Covers the three broken-on-import bugs fixed in Phase 0:

1. `components.observo_api_client` raised `ModuleNotFoundError` on a
   `from .observo import ...` against a non-existent package.
2. `components.s1_models` raised `NameError: Tuple` at class-body
   evaluation because `Tuple` was missing from the typing import.
3. `components.transform_executor.DataplaneExecutor.execute` raised
   `NameError: SecurityError` on the path-validation branches at lines
   120 and 130 because `SecurityError` was only imported at function
   scope inside `_render_config`.

These tests intentionally do NOT instantiate `DataplaneExecutor` — that
would construct a dataplane runtime. The sandbox/behaviour path for
`SecurityError` is exercised in Phase 1.A.
"""

import pytest  # noqa: F401  (kept for future parametrize)


def test_observo_api_client_imports():
    """observo_api_client.py must import without ModuleNotFoundError."""
    from components.observo_api_client import (  # noqa: F401
        ObservoAPI,
        ObservoAPIError,
        ObservoConnectionError,
        ObservoAuthenticationError,
        ObservoValidationError,
    )


def test_s1_models_tuple_annotation_resolves():
    """s1_models.py must import without NameError on Tuple.

    Touches both `S1QueryValidator.validate_query_syntax` (line 411) and
    `S1ToObservoConverter.convert_field_value` (line 485) to force the
    `Tuple[...]` annotations on those methods to evaluate.
    """
    from components.s1_models import S1QueryValidator, S1ToObservoConverter

    assert callable(getattr(S1QueryValidator, "validate_query_syntax", None))
    assert callable(getattr(S1ToObservoConverter, "convert_field_value", None))


def test_transform_executor_security_error_is_importable():
    """The SecurityError symbol must resolve at the module level where
    `DataplaneExecutor.execute` raises it (lines 120 and 130).

    We only verify the import surface here; actually triggering the
    raise path would construct a dataplane runtime, which belongs to
    Phase 1.A.
    """
    from components.transform_executor import DataplaneExecutor
    from components.dataplane_validator import SecurityError

    assert SecurityError is not None
    assert DataplaneExecutor is not None
    # Confirm the symbol is resolvable from the transform_executor module
    # namespace (i.e. the import was promoted to module level, not left
    # function-local).
    import components.transform_executor as te

    assert getattr(te, "SecurityError", None) is SecurityError
