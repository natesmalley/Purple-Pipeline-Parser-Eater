"""Shared Lua entry-function signature detection.

Single source of truth for detecting processEvent/transform/process
signatures in Lua code. All consumers should import from here.
"""

import re
from typing import NamedTuple, Optional


class SignatureInfo(NamedTuple):
    """Result of detecting the entry function signature in Lua code."""
    name: Optional[str]       # "processEvent", "transform", "process", or None
    parameter: Optional[str]  # The parameter name (e.g., "event", "record")
    count: int                # Number of distinct entry functions found


# Canonical patterns — single source of truth
# Priority order: processEvent > process > transform (matches harness contract)
_SIGNATURES = [
    ("processEvent", re.compile(r'function\s+processEvent\s*\(([^)]*)\)')),
    ("process", re.compile(r'function\s+process\s*\(([^)]*)\)')),
    ("transform", re.compile(r'function\s+transform\s*\(([^)]*)\)')),
]


def detect_entry_signature(lua_code: str) -> SignatureInfo:
    """Detect the entry function signature in Lua code.

    Priority order: processEvent > process > transform.
    Returns SignatureInfo with the detected function name, parameter,
    and total count of entry function types found.
    """
    found_name: Optional[str] = None
    found_param: Optional[str] = None
    total_count = 0

    for name, pattern in _SIGNATURES:
        matches = pattern.findall(lua_code)
        if matches:
            if found_name is None:
                found_name = name
                found_param = matches[0].strip() if matches[0] else None
            total_count += 1

    return SignatureInfo(name=found_name, parameter=found_param, count=total_count)


def has_signature(lua_code: str, name: str) -> bool:
    """Check if a specific entry function signature exists."""
    for sig_name, pattern in _SIGNATURES:
        if sig_name == name and pattern.search(lua_code):
            return True
    return False
