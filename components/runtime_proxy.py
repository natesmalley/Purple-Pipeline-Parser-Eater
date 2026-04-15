"""Stream A2.b — web-side runtime shim with a pending-requests file.

The split-topology web (gunicorn) process does NOT own the worker's
in-process queues. This shim lets the routes at
``components/web_ui/routes.py:3589-3642`` keep working unchanged by
duck-typing the same five method names that ``ContinuousConversionService``
exposes on the daemon path.

Contract:

- POST /runtime/reload/<id>     -> ``request_runtime_reload``
- DELETE /runtime/reload/<id>   -> ``pop_runtime_reload``
- POST /runtime/canary/<id>...  -> ``request_canary_promotion``
- DELETE /runtime/canary/<id>.. -> ``pop_canary_promotion``
- GET /runtime/status           -> ``get_runtime_status``

POST writes the parser_id into the local ``pending_requests.json`` ledger AND
appends a record to the FeedbackChannel so the worker actually does the work.
DELETE removes the parser_id from the ledger (cancel-or-ack semantics): if it
was present, return the parser_id (route returns 200); otherwise return None
(route returns 404).
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

from components.feedback_channel import FeedbackChannel

logger = logging.getLogger(__name__)


@dataclass
class RuntimeProxy:
    """Web-side shim over the worker's runtime services."""

    feedback_channel: FeedbackChannel
    snapshot_path: Path
    pending_requests_path: Path
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    def __post_init__(self) -> None:
        self.snapshot_path = Path(self.snapshot_path)
        self.pending_requests_path = Path(self.pending_requests_path)

    # ---- read-only: worker's persisted snapshot ----

    def get_runtime_status(self) -> Dict:
        """Read the worker's last persisted runtime snapshot.

        Returns an empty-but-well-shaped dict when the snapshot doesn't
        exist yet (cold start). Shape mirrors
        ``ContinuousConversionService.get_runtime_status``.
        """
        with self._lock:
            try:
                return json.loads(self.snapshot_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return {
                    "runtime_services": [],
                    "reloads_pending": [],
                    "canary_pending": [],
                }

    # ---- pending_requests.json helpers ----

    def _read_pending(self) -> Dict[str, list]:
        try:
            data = json.loads(
                self.pending_requests_path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError):
            return {"runtime_reload": [], "canary_promotion": []}
        data.setdefault("runtime_reload", [])
        data.setdefault("canary_promotion", [])
        return data

    def _write_pending_atomic(self, data: Dict) -> None:
        self.pending_requests_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(
            dir=str(self.pending_requests_path.parent),
            prefix=".rp_",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, sort_keys=True)
            os.replace(tmp, self.pending_requests_path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    # ---- runtime reload ----

    def request_runtime_reload(self, parser_id: str) -> bool:
        """Idempotent — re-requesting a parser_id already in the set is not
        an error and still returns True."""
        with self._lock:
            data = self._read_pending()
            if parser_id not in data["runtime_reload"]:
                data["runtime_reload"].append(parser_id)
                self._write_pending_atomic(data)
        try:
            self.feedback_channel.append({
                "action": "runtime_reload_request",
                "parser_id": parser_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as exc:
            logger.warning(
                "RuntimeProxy: feedback channel append failed for reload %s: %s",
                parser_id, exc,
            )
        return True

    def pop_runtime_reload(self, parser_id: str) -> Optional[str]:
        with self._lock:
            data = self._read_pending()
            if parser_id in data["runtime_reload"]:
                data["runtime_reload"].remove(parser_id)
                self._write_pending_atomic(data)
                return parser_id
            return None

    # ---- canary promotion (same shape) ----

    def request_canary_promotion(self, parser_id: str) -> bool:
        with self._lock:
            data = self._read_pending()
            if parser_id not in data["canary_promotion"]:
                data["canary_promotion"].append(parser_id)
                self._write_pending_atomic(data)
        try:
            self.feedback_channel.append({
                "action": "canary_promotion_request",
                "parser_id": parser_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as exc:
            logger.warning(
                "RuntimeProxy: feedback channel append failed for canary %s: %s",
                parser_id, exc,
            )
        return True

    def pop_canary_promotion(self, parser_id: str) -> Optional[str]:
        with self._lock:
            data = self._read_pending()
            if parser_id in data["canary_promotion"]:
                data["canary_promotion"].remove(parser_id)
                self._write_pending_atomic(data)
                return parser_id
            return None
