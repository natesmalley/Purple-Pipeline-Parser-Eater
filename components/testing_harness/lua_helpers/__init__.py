"""Canonical Lua helper functions loader.

Single source of truth for OCSF helper functions used in both the LLM
prompt template and the harness sandbox runtime.
"""

from pathlib import Path
from typing import Optional

_HELPERS_PATH = Path(__file__).parent / "ocsf_helpers.lua"
_cached_source: Optional[str] = None


def get_canonical_helpers() -> str:
    """Return the canonical Lua helper source code."""
    global _cached_source
    if _cached_source is None:
        _cached_source = _HELPERS_PATH.read_text(encoding="utf-8")
    return _cached_source


def get_helpers_for_prompt() -> str:
    """Return helpers formatted for embedding in the LLM system prompt."""
    return (
        "=== PRODUCTION HELPER FUNCTIONS (copy these verbatim) ===\n\n"
        + get_canonical_helpers()
    )
