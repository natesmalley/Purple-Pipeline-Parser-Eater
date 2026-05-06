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
                # FU18 DA-FU17 F9: millisecond-resolution timestamp.
                # Pre-FU18 the format was second-resolution, which left a
                # 1-second collision window where two rotations in the
                # same second would overwrite each other's archive (e.g.
                # under a tight load-test loop or a rotation triggered
                # concurrently by two processes that both held a fresh
                # advisory lock across a >50MB-burst boundary). Bumping
                # to ms resolution shrinks the collision window by 1000x
                # to a 1-millisecond burst, which is below the realistic
                # rotation cadence even on stress-test workloads.
                now = datetime.now(timezone.utc)
                date_str = (
                    now.strftime("%Y%m%d-%H%M%S-")
                    + f"{now.microsecond // 1000:03d}"
                )
                # FU18 DA-FU17 F7: atomic-rename rotation eliminates the
                # read-then-truncate race. The pre-FU18 sequence
                #   read live -> gzip-write archive -> truncate live
                # opened a window where any concurrent ``record()`` on
                # another fd-or-process landed BETWEEN the read and the
                # truncate, so the appended bytes were lost on truncate.
                # The atomic rename below is the standard log-rotation
                # idiom: in-flight writers' open fds keep pointing at the
                # archived inode (unix semantics — fd refs the inode, not
                # the path), so their writes naturally drain into the
                # archive we then gzip and unlink. New writers see the
                # fresh empty file via O_CREAT on their next ``os.open``.
                plain_archive = self.path.with_name(
                    f"cost_ledger.{date_str}.jsonl"
                )
                gz_archive = self.path.with_name(
                    f"cost_ledger.{date_str}.jsonl.gz"
                )
                # FU18 DA-FU18 C7 (BLOCKING fix): use ``os.replace`` not
                # ``os.rename``. Per CLAUDE.md, the production deployment
                # target includes Docker Desktop on Windows, where
                # ``os.rename`` semantics differ from POSIX:
                #   - POSIX: atomic replace; in-flight writers' fds keep
                #     pointing at the renamed inode.
                #   - Windows: ``os.rename`` FAILS if the destination
                #     exists, and may fail if the source is open
                #     concurrently (sharing-mode dependent).
                # ``os.replace`` is cross-platform-safe — POSIX-equivalent
                # on Linux, replaces existing destination on Windows.
                # The dated archive path includes ms resolution and a
                # uniqueness check via the lock, so destination collision
                # is unlikely in practice but the right primitive is
                # ``os.replace`` regardless.
                os.replace(str(self.path), str(plain_archive))
                # gzip-and-drain the renamed file. Stream via writelines
                # rather than ``read()`` so a 50MB+ file doesn't pin the
                # full size in memory at once.
                try:
                    with open(plain_archive, "rb") as src, gzip.open(
                        str(gz_archive), "wb"
                    ) as dst:
                        dst.writelines(src)
                    os.unlink(plain_archive)
                except Exception:
                    # If gzip fails partway, leave the plain rotated file
                    # in place rather than losing the archive — the
                    # operator can manually gzip later. Re-raise so the
                    # outer ``except`` logs and continues.
                    raise
                logger.info("Rotated cost ledger to %s", gz_archive)
        except portalocker.LockException:
            logger.debug(
                "cost ledger rotation lock unavailable; another process is rotating"
            )
        except Exception as exc:  # noqa: BLE001
            # Rotation failures must NEVER block a record(); log and continue.
            logger.warning("cost ledger rotation failed: %s", exc)


# Module-level singleton (mirrors get_global_store pattern from settings_store).
_default_ledger: Optional[CostLedger] = None
# FU18 DA-FU17 F8: thread-safe singleton init lock. Pre-FU18, the
# check-then-set in ``get_default_ledger`` raced when two threads called
# simultaneously: thread A would see ``None`` and start constructing,
# thread B would race past the same ``None`` check and construct a
# second ``CostLedger`` instance. Both instances bind to the same path
# (so cross-process O_APPEND atomicity still held), but each carried
# its own ``threading.Lock`` and rotation-check counter — defeating the
# in-process serialization the docstring promises and producing
# nondeterministic doubled rotation triggers under load. Double-checked
# locking with a re-check inside the lock is the standard fix.
_default_ledger_lock = threading.Lock()


def get_default_ledger() -> CostLedger:
    """Return the process-wide default cost ledger.

    Lazy-initialized on first access. Path resolved via ``COST_LEDGER_PATH``
    env var or defaults to ``data/runtime/cost_ledger.jsonl``.

    FU18 DA-FU17 F8: singleton init is thread-safe via double-checked
    locking. The initial ``is None`` check stays unlocked so the
    steady-state hot path (post-init) doesn't pay a lock acquire on
    every call; the lock guards only the cold construction path.
    """
    global _default_ledger
    if _default_ledger is None:
        with _default_ledger_lock:
            # Re-check inside lock — another thread may have constructed
            # while we were waiting on the lock acquire.
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
