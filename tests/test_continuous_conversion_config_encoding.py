"""FU1 — regression test for explicit UTF-8 encoding on config read.

Before the fix, ``ContinuousConversionService.initialize()`` opened
``config.yaml`` without an explicit ``encoding=`` argument. On Windows the
platform default is ``cp1252`` (``charmap``), which raises
``UnicodeDecodeError`` on common UTF-8 bytes such as the ``é`` (U+00E9 →
``0xC3 0xA9``) sequence. Linux containers default to UTF-8 and were
unaffected.

The fix pins ``encoding='utf-8'`` at the only relevant ``open()`` call.

This test exercises the actual production read path by:

1. Writing a UTF-8-encoded config to ``tmp_path``.
2. Constructing :class:`ContinuousConversionService` with that path.
3. Driving ``initialize()`` up to (but not past) the YAML parse step, by
   monkeypatching ``yaml.safe_load`` in the service's module namespace to
   raise a sentinel exception. Reaching that sentinel proves the
   ``open(...).read()`` step succeeded — i.e. the encoding fix is in force.

The point of the test is that the read does NOT raise
``UnicodeDecodeError`` on any platform; everything past the read is out
of scope.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

import continuous_conversion_service as ccs


_NON_ASCII_CONFIG = (
    "# comment with é and ☃ — non-ASCII bytes that crash cp1252\n"
    "logging:\n"
    "  level: INFO\n"
    "service:\n"
    "  name: parser-eater-fu1\n"
)


class _SentinelStop(Exception):
    """Raised by the patched yaml.safe_load to stop initialize() after the read."""


def test_initialize_reads_utf8_config_without_unicode_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The config read must accept UTF-8 bytes regardless of platform default."""
    config_path = tmp_path / "config.yaml"
    # Write explicitly as UTF-8 so the bytes on disk include é (0xC3 0xA9)
    # and a snowman (0xE2 0x98 0x83) — both invalid under cp1252.
    config_path.write_text(_NON_ASCII_CONFIG, encoding="utf-8")
    # Sanity-check: bytes on disk are UTF-8, not the system default.
    raw = config_path.read_bytes()
    assert b"\xc3\xa9" in raw, "test fixture must contain UTF-8 'é' bytes"

    service = ccs.ContinuousConversionService(
        config_path=config_path, worker_only=True
    )

    # Stop initialize() right after the read+expand, before it tries to
    # construct settings / RAG / SDL singletons. Reaching this sentinel
    # proves the open(...).read() step did not raise UnicodeDecodeError.
    def _fake_safe_load(_text: str) -> None:
        raise _SentinelStop("read succeeded")

    monkeypatch.setattr(ccs.yaml, "safe_load", _fake_safe_load)

    with pytest.raises(_SentinelStop):
        asyncio.run(service.initialize())


def test_initialize_does_not_raise_unicode_decode_error_explicit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Belt-and-suspenders: explicitly assert UnicodeDecodeError never fires."""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(_NON_ASCII_CONFIG, encoding="utf-8")

    service = ccs.ContinuousConversionService(
        config_path=config_path, worker_only=True
    )

    def _fake_safe_load(_text: str) -> None:
        raise _SentinelStop("read succeeded")

    monkeypatch.setattr(ccs.yaml, "safe_load", _fake_safe_load)

    try:
        asyncio.run(service.initialize())
    except UnicodeDecodeError as exc:  # pragma: no cover - regression guard
        pytest.fail(f"config read raised UnicodeDecodeError: {exc!r}")
    except _SentinelStop:
        pass
    except Exception:
        # Any other failure mode means the read succeeded; that's the
        # contract we care about for FU1.
        pass
