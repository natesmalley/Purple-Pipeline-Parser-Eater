"""FU17 — Append-only JSONL cost ledger for LLM API call telemetry.

Mirrors ``components/feedback_channel.py`` exactly: ``O_APPEND`` + single
``os.write`` atomic-append pattern. Cross-process atomicity comes from
``O_APPEND`` + ``MAX_RECORD_BYTES`` cap (POSIX guarantees atomic writes
<= ``PIPE_BUF`` / 4 KiB on Linux/Darwin on an ``O_APPEND``-opened file).

NOT for storing user input or LLM output bodies — only per-API-call
telemetry: provider, model, tokens, latency, finish_reason. Score is
computed AFTER the API call returns, so it is captured by a separate
path (the harness report); pulling it back into the ledger would invert
the call hierarchy.

Design contract (locked through plan-review round 6):
  - Single ``os.write`` of (``json.dumps(record) + "\\n"``) to an
    ``O_APPEND`` fd. NEVER ``tempfile + os.replace`` (that's overwrite,
    not append).
  - Record size <= ``MAX_RECORD_BYTES = 2048`` (PIPE_BUF guarantee floor).
  - ``threading.Lock`` for own-process thread serialization (matches
    feedback_channel exactly). Cross-process atomicity is from
    ``O_APPEND``, NOT the lock.
  - File mode 0640 (per FU17 spec; feedback_channel uses 0644).
  - Failed-call rows are recorded too (tokens=0, finish_reason=type name)
    to capture cost-of-failure.
  - Rotation at 50 MB to dated gzip archive, guarded by portalocker
    advisory lock so concurrent processes don't race the rotation.
"""
from __future__ import annotations

import gzip
import json
import logging
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# POSIX PIPE_BUF guarantee floor (matches feedback_channel.py:29). Encoded
# records must be <= this byte count for the O_APPEND atomic-write contract
# to hold. The cap exists because POSIX only guarantees atomicity for
# write(2) calls of size <= PIPE_BUF (4 KiB on Linux); we use 2 KiB to
# leave headroom for filesystem-level encoding overhead.
MAX_RECORD_BYTES = 2048

# Rotation: when the live ledger exceeds this size, archive to a dated
# .jsonl.gz alongside and truncate the live file. 50 MB at ~500 bytes per
# record allows ~100k records per archive — plenty for monthly windows on
# a normal-load deployment.
ROTATION_THRESHOLD_BYTES = 50 * 1024 * 1024  # 50 MB

# Stat-and-maybe-rotate is a non-trivial syscall, so we only check size
# 1-in-N records. With N=100 the worst-case overshoot at typical record
# sizes (~500 B) is ~50 KiB beyond the threshold, which is negligible.
ROTATION_CHECK_EVERY_N_RECORDS = 100


@dataclass
class CostLedger:
    """Process-safe append-only JSONL cost ledger.

    Default path: ``data/runtime/cost_ledger.jsonl`` (mode 0640).

    Cross-process atomicity contract:
      - Single ``os.write`` of (``json.dumps(record) + "\\n"``) to an
        ``O_APPEND`` fd.
      - Record size <= ``MAX_RECORD_BYTES`` (PIPE_BUF guarantee floor).
      - ``threading.Lock`` serializes own-process threads (matches
        ``feedback_channel.FeedbackChannel`` pattern).
      - Cross-process atomicity comes from ``O_APPEND``, NOT from the lock.
    """

    path: Path
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _writes_since_rotation_check: int = field(default=0, repr=False)

    def __post_init__(self) -> None:
        # Accept str / os.PathLike too — normalize to Path so the rest of
        # the class can rely on Path semantics.
        self.path = Path(self.path)

    def record(
        self,
        *,
        parser_name: str,
        provider: str,
        model: str,
        iteration: int,
        tokens_in: int,
        tokens_out: int,
        cache_read: int = 0,
        thinking_tokens: Optional[int] = None,
        cache_breakpoints_used: int = 0,
        response_id: Optional[str] = None,
        finish_reason: str = "",
        latency_ms: int = 0,
        retry_attempt: int = 0,
    ) -> None:
        """Atomically append a single cost-row JSON object.

        Schema is fixed and intentionally narrow — NO PII, NO Lua bodies,
        NO prompt text. If you find yourself wanting to add a field that
        could carry user-pasted samples or model output, route it through
        a separate logger and KEEP IT OUT of this ledger.

        ``retry_attempt`` (FU17 round-2 / Fix 3): disambiguates the
        truncation-retry double-record. ``_call_llm`` may call
        ``_invoke_provider`` twice for one logical user-visible call —
        first attempt at the configured ``max_tokens``, second attempt
        with the bumped ceiling. Consumers that want unique
        user-visible-call counts aggregate by
        ``(parser_name, iteration, retry_attempt=0)``; consumers that
        want raw API-call counts include all rows. Default 0 = first
        (and usually only) attempt.

        Raises:
          ValueError if the encoded record exceeds ``MAX_RECORD_BYTES`` or
            contains a literal newline (would corrupt JSONL framing).
          OSError on disk write failure (open / write surface).
        """
        record: Dict[str, Any] = {
            # ISO-8601 UTC, milliseconds-only, "Z" suffix for parser-friendliness
            "ts": (
                datetime.now(timezone.utc)
                .isoformat(timespec="milliseconds")
                .replace("+00:00", "Z")
            ),
            "parser_name": parser_name,
            "provider": provider,
            "model": model,
            "iteration": iteration,
            "retry_attempt": retry_attempt,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "cache_read": cache_read,
            "thinking_tokens": thinking_tokens,
            "cache_breakpoints_used": cache_breakpoints_used,
            "response_id": response_id,
            "finish_reason": finish_reason,
            "latency_ms": latency_ms,
        }
        encoded = json.dumps(record, sort_keys=True, default=str)
        if "\n" in encoded:
            # JSON serialization should never emit a literal newline, but
            # belt-and-suspenders: a stray newline would corrupt JSONL
            # framing. Reject rather than silently mangle.
            raise ValueError(
                "encoded cost record contains literal newline "
                "(would corrupt JSONL framing)"
            )
        line = encoded + "\n"
        encoded_bytes = line.encode("utf-8")
        if len(encoded_bytes) > MAX_RECORD_BYTES:
            raise ValueError(
                f"cost record exceeds {MAX_RECORD_BYTES} byte cap "
                f"(got {len(encoded_bytes)} bytes — exceeds PIPE_BUF guarantee)"
            )

        # Ensure parent dir exists (analogous to feedback_channel:62).
        self.path.parent.mkdir(parents=True, exist_ok=True)

        # Process-local lock to keep our own threads serialized; cross-process
        # atomicity comes from O_APPEND + the size cap.
        with self._lock:
            fd = os.open(
                str(self.path),
                os.O_WRONLY | os.O_CREAT | os.O_APPEND,
                0o640,  # FU17 plan spec: mode 0640 (NOT 0644)
            )
            try:
                os.write(fd, encoded_bytes)
                try:
                    os.fsync(fd)
                except OSError:
                    # fsync may fail on certain mounts (e.g. tmpfs); the
                    # write itself succeeded, so log and continue.
                    logger.debug("fsync failed for cost ledger %s", self.path)
            finally:
                os.close(fd)

            # Rotation check — sampled to keep the hot path light.
            self._writes_since_rotation_check += 1
            if self._writes_since_rotation_check >= ROTATION_CHECK_EVERY_N_RECORDS:
                self._writes_since_rotation_check = 0
                self._maybe_rotate()

    # ------------------------------------------------------------------ #
    # Rotation                                                            #
    # ------------------------------------------------------------------ #

    def _maybe_rotate(self) -> None:
        """If the file size exceeds ``ROTATION_THRESHOLD_BYTES``, rotate
        to a dated gzip archive and truncate the live file.

        Uses ``portalocker`` advisory locking (the same library
        ``state_store.py`` uses) so that two processes don't both rotate
        at once and double-archive. If portalocker isn't installed (it's
        a hard dep in ``requirements.txt`` but tests may install a slim
        env), rotation is skipped with a warning rather than crashing.
        """
        try:
            size = self.path.stat().st_size
        except FileNotFoundError:
            return
        except OSError as exc:
            logger.warning("cost ledger stat failed: %s", exc)
            return
        if size < ROTATION_THRESHOLD_BYTES:
            return

        try:
            import portalocker
        except ImportError:
            logger.warning(
                "portalocker not available; skipping cost ledger rotation"
            )
            return

        lock_path = self.path.with_suffix(".rotation.lock")
        try:
            with portalocker.Lock(str(lock_path), timeout=1):
                # Re-check inside lock — another process may have rotated
                # while we were waiting on the advisory lock.
                try:
                    cur_size = self.path.stat().st_size
                except FileNotFoundError:
                    return
                if cur_size < ROTATION_THRESHOLD_BYTES:
                    return
                date_str = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
                archive_path = self.path.with_name(
                    f"cost_ledger.{date_str}.jsonl.gz"
                )
                # Read live -> gzip-write archive. Loaded fully into memory
                # because gzip.open's stream-mode adds little benefit at
                # 50 MB (still finishes in well under a second on any
                # modern disk) and is harder to reason about under failure.
                with open(self.path, "rb") as src, gzip.open(archive_path, "wb") as dst:
                    dst.write(src.read())
                # Truncate the live file rather than delete it — a
                # concurrent reader holding an fd on the live file would
                # see content disappear under it if we unlinked.
                with open(self.path, "wb"):
                    pass
                logger.info("Rotated cost ledger to %s", archive_path)
        except portalocker.LockException:
            logger.debug(
                "cost ledger rotation lock unavailable; another process is rotating"
            )
        except Exception as exc:  # noqa: BLE001
            # Rotation failures must NEVER block a record(); log and continue.
            logger.warning("cost ledger rotation failed: %s", exc)


# Module-level singleton (mirrors get_global_store pattern from settings_store).
_default_ledger: Optional[CostLedger] = None


def get_default_ledger() -> CostLedger:
    """Return the process-wide default cost ledger.

    Lazy-initialized on first access. Path resolved via ``COST_LEDGER_PATH``
    env var or defaults to ``data/runtime/cost_ledger.jsonl``.
    """
    global _default_ledger
    if _default_ledger is None:
        path_str = os.environ.get(
            "COST_LEDGER_PATH",
            "data/runtime/cost_ledger.jsonl",
        )
        _default_ledger = CostLedger(path=Path(path_str))
    return _default_ledger


def set_default_ledger(ledger: Optional[CostLedger]) -> None:
    """Override (or reset to None for re-init) the singleton.

    ``None`` is accepted so tests can reset between runs and have the
    next ``get_default_ledger()`` call re-resolve env / defaults.
    """
    global _default_ledger
    _default_ledger = ledger
