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
from typing import Final, List

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

# Sentinel marker injected at the top of every wrapped output. Its presence is
# the primary idempotence signal: if we see this line, the body is known-wrapped
# and re-wrapping is refused. A secondary heuristic (see ``wrap_for_observo``)
# strips comments and string literals before looking for a literal
# ``function process(event, emit)`` signature so that authored bodies that
# merely mention the wrapper in a comment or a string are NOT mis-detected.
_WRAPPED_SENTINEL: Final[str] = "-- [wrap_for_observo] deploy-ready; do not edit by hand"


def _strip_lua_comments_and_strings(src: str) -> str:
    """Strip Lua line comments, block comments, and string literals.

    Best-effort (not a full Lua lexer). Handles:

    - Single-line ``--`` comments (stop at newline, but NOT ``--[[``)
    - Block comments ``--[[ ... ]]``
    - Double-quoted string literals ``"..."`` (with ``\\`` escape)
    - Single-quoted string literals ``'...'`` (with ``\\`` escape)

    Does NOT handle long-bracket string literals ``[[ ... ]]`` or level-N
    long brackets (``[==[ ... ]==]``). For the idempotence check, best-effort
    is sufficient — the sentinel marker is the primary signal and this is
    a belt-and-braces second line of defense.
    """
    out: List[str] = []
    i = 0
    n = len(src)
    while i < n:
        c = src[i]
        # Block comment --[[ ... ]]
        if c == "-" and i + 3 < n and src[i:i + 4] == "--[[":
            end = src.find("]]", i + 4)
            if end == -1:
                break
            i = end + 2
            continue
        # Line comment -- ...
        if c == "-" and i + 1 < n and src[i + 1] == "-":
            end = src.find("\n", i + 2)
            if end == -1:
                break
            i = end + 1
            continue
        # Double-quoted string
        if c == '"':
            i += 1
            while i < n and src[i] != '"':
                if src[i] == "\\" and i + 1 < n:
                    i += 2
                else:
                    i += 1
            i += 1
            continue
        # Single-quoted string
        if c == "'":
            i += 1
            while i < n and src[i] != "'":
                if src[i] == "\\" and i + 1 < n:
                    i += 2
                else:
                    i += 1
            i += 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


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
        The full deploy-ready Lua script with the sentinel marker, inlined
        helpers (optional), the authored ``processEvent`` body, and the outer
        ``process(event, emit)`` wrapper.

    Raises:
        ValueError: If ``lua_body`` is already wrapped. Two detection paths:
            (1) Primary: presence of the ``_WRAPPED_SENTINEL`` marker. (2)
            Secondary heuristic: a literal ``function process(event, emit)``
            signature that survives comment/string stripping. Callers should
            wrap exactly once, at the final emit boundary. For an idempotent
            variant that returns already-wrapped bodies unchanged, see
            :func:`ensure_wrapped`.
    """
    # Primary detection: sentinel marker
    if _WRAPPED_SENTINEL in lua_body:
        raise ValueError(
            "lua_body is already wrapped by wrap_for_observo "
            f"(found sentinel marker {_WRAPPED_SENTINEL!r}). "
            "Do not wrap twice."
        )

    # Secondary heuristic: the literal outer-wrapper signature outside of
    # comments/strings. Authored bodies that only mention the signature in
    # a comment or a string literal do NOT trip this check.
    code_only = _strip_lua_comments_and_strings(lua_body)
    if "function process(event, emit)" in code_only:
        raise ValueError(
            "lua_body appears to already define function process(event, emit). "
            "Do not wrap twice."
        )

    parts: List[str] = [_WRAPPED_SENTINEL]
    if include_helpers:
        helpers = get_canonical_helpers()
        parts.append(helpers.rstrip())
        parts.append("")
    parts.append(lua_body.rstrip())
    parts.append("")
    parts.append(_OUTER_WRAPPER)
    return "\n".join(parts)


def ensure_wrapped(lua_body: str, *, include_helpers: bool = True) -> str:
    """Idempotent sibling of :func:`wrap_for_observo`.

    Returns ``lua_body`` unchanged if it's already wrapped (detected by the
    ``_WRAPPED_SENTINEL`` marker). Otherwise calls :func:`wrap_for_observo`
    and returns the wrapped output.

    Use this at emit sites that might receive either an authored body OR an
    already-wrapped body (e.g. ``lua_exporter.build_lua_content`` which can be
    fed either ``entry.lua_script`` from an upstream generator that already
    wrapped, or the ``GENERIC_EXTRACTION_LUA`` fallback that is raw).

    Generator emit sites that should always wrap exactly once should keep
    calling :func:`wrap_for_observo` directly so a double-wrap bug surfaces
    loudly as ``ValueError``.
    """
    if _WRAPPED_SENTINEL in lua_body:
        return lua_body
    return wrap_for_observo(lua_body, include_helpers=include_helpers)
