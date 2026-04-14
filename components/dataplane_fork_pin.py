"""Dataplane fork BuildID pinning - plan Phase 5.C.

The Purple Pipeline Parser Eater generates YAML + Lua targeting a specific
Observo dataplane fork. Binary symbol audit (see CLAUDE.md "Observo runtime
reality") verified the audited fork as:
  - Vector 0.44.7
  - git SHA dbac53e
  - build timestamp 2025-10-15 12:43:52
  - BuildID 5de1d972760330258cda3554c36e67cae5c57bde

If an operator runs the harness against a binary with a different BuildID,
generated configs may not validate. This module provides a non-blocking
startup assertion that logs a warning in that case.

Environment variable overrides:
  ALLOW_UNKNOWN_DATAPLANE=1   - suppress the warning entirely
  DATAPLANE_BINARY_PATH=<path> - override the default binary lookup
"""
from __future__ import annotations

import logging
import os
import struct
import threading
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

EXPECTED_BUILD_ID = "5de1d972760330258cda3554c36e67cae5c57bde"
EXPECTED_VECTOR_VERSION = "0.44.7"
EXPECTED_GIT_SHA = "dbac53e"
EXPECTED_BUILD_TIMESTAMP = "2025-10-15 12:43:52"

_DEFAULT_BINARY_CANDIDATES = (
    "/usr/local/bin/dataplane",
    "/opt/observo/bin/dataplane",
    "./dataplane",
    "./dataplane.amd64",
)

_already_checked_lock = threading.Lock()
_already_checked = False


def _extract_build_id_from_elf(binary_path: Path) -> Optional[str]:
    """Extract the .note.gnu.build-id section from an ELF binary.

    Returns the hex-encoded BuildID string or None if extraction fails.
    This is a minimal ELF parser - it walks the section headers looking
    for SHT_NOTE entries with name "GNU" and type NT_GNU_BUILD_ID (3).
    No external deps; uses only struct + Path.read_bytes.
    """
    try:
        data = binary_path.read_bytes()
    except (OSError, PermissionError):
        return None

    if len(data) < 64 or data[:4] != b"\x7fELF":
        return None

    ei_class = data[4]
    if ei_class != 2:  # 64-bit
        return None

    # Parse ELF64 header
    try:
        e_shoff = struct.unpack_from("<Q", data, 40)[0]
        e_shentsize = struct.unpack_from("<H", data, 58)[0]
        e_shnum = struct.unpack_from("<H", data, 60)[0]
        e_shstrndx = struct.unpack_from("<H", data, 62)[0]
    except struct.error:
        return None

    if e_shnum == 0 or e_shentsize == 0:
        return None

    # Read section header string table
    try:
        shstr_off = struct.unpack_from("<Q", data, e_shoff + e_shstrndx * e_shentsize + 24)[0]
        shstr_size = struct.unpack_from("<Q", data, e_shoff + e_shstrndx * e_shentsize + 32)[0]
    except struct.error:
        return None

    shstrtab = data[shstr_off:shstr_off + shstr_size]

    # Walk sections looking for .note.gnu.build-id
    for i in range(e_shnum):
        base = e_shoff + i * e_shentsize
        try:
            sh_name = struct.unpack_from("<I", data, base)[0]
            sh_type = struct.unpack_from("<I", data, base + 4)[0]
            sh_off = struct.unpack_from("<Q", data, base + 24)[0]
            sh_size = struct.unpack_from("<Q", data, base + 32)[0]
        except struct.error:
            continue

        if sh_type != 7:  # SHT_NOTE
            continue

        name_end = shstrtab.find(b"\x00", sh_name)
        if name_end == -1:
            continue
        section_name = shstrtab[sh_name:name_end].decode("ascii", errors="replace")
        if section_name != ".note.gnu.build-id":
            continue

        # Parse the note: namesz(4) descsz(4) type(4) name(4-aligned) desc(4-aligned)
        if sh_size < 12:
            return None
        try:
            namesz = struct.unpack_from("<I", data, sh_off)[0]
            descsz = struct.unpack_from("<I", data, sh_off + 4)[0]
            note_type = struct.unpack_from("<I", data, sh_off + 8)[0]
        except struct.error:
            return None

        if note_type != 3:  # NT_GNU_BUILD_ID
            continue

        desc_start = sh_off + 12 + ((namesz + 3) & ~3)
        desc = data[desc_start:desc_start + descsz]
        return desc.hex()

    return None


def _find_dataplane_binary() -> Optional[Path]:
    """Locate the dataplane binary. Respects DATAPLANE_BINARY_PATH env."""
    override = os.environ.get("DATAPLANE_BINARY_PATH", "").strip()
    if override:
        p = Path(override)
        return p if p.exists() else None

    for candidate in _DEFAULT_BINARY_CANDIDATES:
        p = Path(candidate)
        if p.exists():
            return p

    return None


def assert_dataplane_fork(*, force: bool = False) -> None:
    """Non-blocking startup assertion.

    Emits a logger.warning if the operator's binary drifts from the audited
    fork. Runs at most once per process unless `force=True`.

    Controlled by ALLOW_UNKNOWN_DATAPLANE env var:
      - "1" / "true" / "yes" -> suppress the warning entirely
      - anything else -> warn on mismatch

    Does NOT raise. Missing binary is silently skipped (dev/test environment).
    """
    global _already_checked
    # Flask is threaded - guard the check/set flag with a lock so two
    # concurrent callers can't both proceed to binary inspection. The race
    # is benign (at worst a duplicate warning log), but the fix is trivial.
    with _already_checked_lock:
        if _already_checked and not force:
            return
        _already_checked = True

    # Rest of the function stays OUTSIDE the lock - we only protect the
    # check/set flag; actual binary inspection is slow and doesn't need
    # lock coverage (worst case: two threads both inspect the binary once
    # across a force=True call, which is fine).

    allow = os.environ.get("ALLOW_UNKNOWN_DATAPLANE", "").strip().lower() in ("1", "true", "yes")
    if allow:
        logger.debug(
            "dataplane_fork_pin: ALLOW_UNKNOWN_DATAPLANE set; skipping BuildID check"
        )
        return

    binary = _find_dataplane_binary()
    if binary is None:
        # Dev/test environment - nothing to check.
        logger.debug("dataplane_fork_pin: no dataplane binary found; skipping BuildID check")
        return

    actual = _extract_build_id_from_elf(binary)
    if actual is None:
        logger.warning(
            "dataplane_fork_pin: could not extract BuildID from %s "
            "(not an ELF64 binary, or .note.gnu.build-id section missing). "
            "Cannot verify fork identity.",
            binary,
        )
        return

    if actual != EXPECTED_BUILD_ID:
        logger.warning(
            "dataplane_fork_pin: BuildID mismatch - operator binary %s has BuildID %s, "
            "but generated configs target Observo fork %s / dbac53e / 2025-10-15 "
            "(BuildID %s). Generated YAML may not validate against this binary. "
            "Set ALLOW_UNKNOWN_DATAPLANE=1 to suppress this warning.",
            binary, actual, EXPECTED_VECTOR_VERSION, EXPECTED_BUILD_ID,
        )
    else:
        logger.info(
            "dataplane_fork_pin: BuildID matches audited fork (Vector %s / %s / %s)",
            EXPECTED_VECTOR_VERSION, EXPECTED_GIT_SHA, EXPECTED_BUILD_TIMESTAMP,
        )
