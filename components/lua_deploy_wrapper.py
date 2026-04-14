"""Single source-of-truth for wrapping generator output into the Observo-invokable
shape. See plan Phase 2.A / 2.B.

The authored contract inside the repo is ``processEvent(event) -> event-or-nil``.
The deployed contract Observo actually invokes is ``process(event, emit)``.
This helper bridges the two by prepending inlined OCSF helpers and appending
the outer ``process(event, emit)`` wrapper that calls the authored
``processEvent``.

Reference wrap sites (run-time, NOT deploy-time emit):

- ``components/transform_executor.py`` composes the outer wrapper in YAML
  ``source:`` at render time via ``dofile`` — the raw ``processEvent`` body is
  written to ``transform.lua`` and the outer ``process(event, emit)`` is
  appended in the rendered config block.
- ``components/dataplane_validator.py`` uses the same YAML-side pattern.

Both of those are local validation / execution wraps; the **deploy emit**
path (cache write, disk export, returned result dict) must self-contain the
full script because downstream consumers cannot synthesize YAML around it.
``wrap_for_observo`` is that self-contained wrap.
"""
from __future__ import annotations

import logging
from typing import Final

from components.testing_harness.lua_helpers import get_canonical_helpers

logger = logging.getLogger(__name__)

_OUTER_WRAPPER: Final[str] = """
function process(event, emit)
    local out = processEvent(event["log"] or event)
    if out ~= nil then
        event["log"] = out
        emit(event)
    end
end
""".rstrip() + "\n"


def wrap_for_observo(lua_body: str, *, include_helpers: bool = True) -> str:
    """Wrap a generated/authored processEvent Lua body into the deploy shape.

    Args:
        lua_body: A Lua script that defines ``function processEvent(event) ... end``.
            Must NOT already contain a ``function process(event, emit)`` outer
            wrapper — that's this helper's job. Idempotence: if the body is
            already wrapped, ``ValueError`` is raised so callers can't
            accidentally double-wrap.
        include_helpers: If True (default), prepend the contents of
            ``ocsf_helpers.lua`` (``getNestedField``, ``setNestedField``,
            ``flattenObject``, etc.) so the emitted script is self-contained.
            Set to False only for tests that verify the raw authored body.

    Returns:
        The full deploy-ready Lua script with inlined helpers (optional) +
        the authored ``processEvent`` body + the outer ``process(event, emit)``
        wrapper.

    Raises:
        ValueError: If ``lua_body`` already contains ``function process(event, emit)``
            (idempotence guard). Callers should wrap exactly once, at the
            final emit boundary.
    """
    if "function process(event, emit)" in lua_body:
        raise ValueError(
            "lua_body is already wrapped with 'function process(event, emit)'. "
            "wrap_for_observo must be called exactly once at the final emit "
            "boundary — do not wrap already-wrapped scripts."
        )

    parts = []
    if include_helpers:
        helpers = get_canonical_helpers()
        parts.append(helpers.rstrip())
        parts.append("")
    parts.append(lua_body.rstrip())
    parts.append("")
    parts.append(_OUTER_WRAPPER)
    return "\n".join(parts)
