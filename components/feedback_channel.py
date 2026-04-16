"""Stream A2.a — file-backed cross-process feedback bus.

Used by the gunicorn web process to enqueue review actions and runtime
requests for the worker daemon. The worker drains via ``drain_new`` from a
persisted offset.

Append uses ``O_APPEND`` + a single ``json.dumps(record) + "\\n"`` write +
``fsync``. Per POSIX, writes <= ``PIPE_BUF`` (4 KiB on Linux) on an
``O_APPEND``-opened file are atomic with respect to other concurrent writers,
so we cap record size at 2 KiB to leave headroom for the trailing newline and
on-disk encoding overhead.

This module deliberately has no external deps beyond the stdlib.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

# Maximum encoded record size. Routes should reject anything larger BEFORE
# calling append() with HTTP 400; this is the last line of defence.
MAX_RECORD_BYTES = 2048


@dataclass
class FeedbackChannel:
    """File-backed JSONL append-only queue with cross-process drain."""

    path: Path
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def __post_init__(self) -> None:
        self.path = Path(self.path)

    # ---- writer side (web process) ----

    def append(self, record: Dict) -> None:
        """Atomically append a JSON record + newline. Raises on oversized
        records (``ValueError``) or disk failure (``IOError``)."""
        encoded = json.dumps(record, sort_keys=True, default=str)
        if "\n" in encoded:
            # JSON serialization should never emit a literal newline, but
            # belt-and-suspenders: a stray newline would corrupt the JSONL
            # framing. Reject rather than silently mangle.
            raise ValueError("encoded record contains newline")
        line = encoded + "\n"
        encoded_bytes = line.encode("utf-8")
        if len(encoded_bytes) > MAX_RECORD_BYTES:
            raise ValueError(
                f"feedback record exceeds {MAX_RECORD_BYTES} byte cap "
                f"(got {len(encoded_bytes)} bytes)"
            )

        # Ensure parent dir exists.
        self.path.parent.mkdir(parents=True, exist_ok=True)

        # Process-local lock to keep our own threads serialized; cross-process
        # atomicity comes from O_APPEND + the size cap.
        with self._lock:
            fd = os.open(
                str(self.path),
                os.O_WRONLY | os.O_CREAT | os.O_APPEND,
                0o644,
            )
            try:
                os.write(fd, encoded_bytes)
                try:
                    os.fsync(fd)
                except OSError:
                    # fsync may fail on certain mounts (e.g. tmpfs); the
                    # write itself succeeded, so log and continue.
                    logger.debug("fsync failed for %s", self.path)
            finally:
                os.close(fd)

    # ---- reader side (worker daemon) ----

    def drain_new(self, since_offset: int) -> Tuple[List[Dict], int]:
        """Return (records, new_offset) for everything appended since
        ``since_offset``. Missing file is treated as empty."""
        try:
            stat = self.path.stat()
        except FileNotFoundError:
            return [], since_offset
        except OSError as exc:
            logger.warning("FeedbackChannel stat failed for %s: %s", self.path, exc)
            return [], since_offset

        size = stat.st_size
        if size <= since_offset:
            return [], since_offset

        try:
            with open(self.path, "rb") as fh:
                fh.seek(since_offset)
                blob = fh.read(size - since_offset)
        except OSError as exc:
            logger.warning("FeedbackChannel read failed for %s: %s", self.path, exc)
            return [], since_offset

        records: List[Dict] = []
        # Find the last full newline so we don't half-parse a record that's
        # currently being appended.
        end = blob.rfind(b"\n")
        if end < 0:
            return [], since_offset
        complete = blob[: end + 1]
        new_offset = since_offset + len(complete)
        for raw_line in complete.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                logger.warning("FeedbackChannel skipping malformed line: %s", exc)
                continue
            records.append(rec)
        return records, new_offset
