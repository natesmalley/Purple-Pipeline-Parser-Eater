"""Shared acceptance helper for Lua persistence sites.

W2 (audit fix 2026-04-29): centralizes the gate that every Lua persistence
site must pass before writing to ``output/``. Wired into:

- ``components/web_ui/example_store.py`` — ``record_run()`` (timestamped
  fail-stream tier under ``output/generated_lua/<parser>/``). Pass the
  full ``harness_report``; the score gate applies.
- ``components/web_ui/parser_workbench.py`` — both agent write sites
  (``build_parser_with_agent``, ``build_from_raw_examples``). Pass the
  full ``harness_report`` so the score gate applies.
- ``components/web_ui/parser_workbench.py`` — deterministic ``build_parser()``
  write site. Pass ``harness_report=None``: the deterministic path runs
  ``build_lua_content`` and never invokes the harness, so only the length
  + identity-passthrough gates apply (defense in depth against a future
  regression in ``build_lua_content``).

The function is deterministic and pure: no I/O, no random, no side effects.
It runs in the harness hot path, so callers can rely on constant-time
behavior on a string the size of a typical Lua transform.

Rejection reasons returned in the second tuple element:

- ``"too_short"`` — the (stripped) Lua body is shorter than ``min_length``.
  The default of 100 chars catches the 45-byte identity-passthrough one-liner
  ``function processEvent(event) return event end`` plus any other empty /
  near-empty bodies.
- ``"identity_passthrough"`` — the (stripped) Lua body is exactly the
  literal one-liner above. This is the dominant C2 contamination shape
  (verified ~1264 files in ``output/generated_lua/``).
- ``"low_confidence_score"`` — a ``harness_report`` was provided AND its
  ``confidence_score`` is below ``min_confidence``. ``confidence_score``
  is set at ``harness_orchestrator.py:180``.
- ``None`` — the Lua body is acceptable.

When ``harness_report`` is ``None`` the score gate is skipped — used by the
deterministic ``build_parser()`` path which never runs the harness.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple


_IDENTITY_PASSTHROUGH = "function processEvent(event) return event end"


def is_acceptable_lua(
    lua_code: str,
    harness_report: Optional[Dict[str, Any]] = None,
    *,
    min_confidence: int = 70,
    min_length: int = 100,
) -> Tuple[bool, Optional[str]]:
    """Return ``(accepted, rejection_reason)`` for a Lua body.

    ``rejection_reason`` is one of ``"too_short"``,
    ``"identity_passthrough"``, ``"low_confidence_score"``, or ``None``
    when accepted. See the module docstring for what each means and when
    callers should pass ``harness_report=None``.
    """
    stripped = (lua_code or "").strip()

    if len(stripped) < min_length:
        return False, "too_short"

    if stripped == _IDENTITY_PASSTHROUGH:
        return False, "identity_passthrough"

    if harness_report is not None:
        try:
            score = int(harness_report.get("confidence_score", 0) or 0)
        except (TypeError, ValueError):
            score = 0
        if score < min_confidence:
            return False, "low_confidence_score"

    return True, None
