"""Thread+async-safe state store for the conversion pipeline daemon.

Plan Phase 6.D. Wraps pending_conversions / approved_conversions /
rejected_conversions / modified_conversions behind an asyncio.Lock + a
threading.Lock. Async code (the conversion loop) grabs the asyncio.Lock;
sync code (Flask route handlers on WSGI threads) grabs the threading.Lock.
Both locks are acquired in a fixed order to avoid deadlock; the async path
also briefly acquires the threading lock to stay atomic versus sync callers.

This is NOT a full transactional store — it's a small wrapper around four
dicts with per-operation atomicity. Multi-dict transactions (e.g. "move
from pending to approved in one shot") are explicit methods, not composed
from basic operations.

The store's API matches what continuous_conversion_service.py and
web_ui/routes.py already do to the raw dicts — callers can migrate
incrementally by replacing ``self.pending_conversions[k] = v`` with
``await self.state.aput_pending(k, v)`` (async) or
``self.state.put_pending(k, v)`` (sync).
"""
from __future__ import annotations

import asyncio
import logging
import threading
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional, Tuple

logger = logging.getLogger(__name__)


class StateStore:
    """Async+thread-safe wrapper around the daemon's four conversion dicts.

    Lock ordering (to avoid deadlock): the async path acquires the
    ``asyncio.Lock`` first, then briefly the ``threading.RLock`` for the
    actual dict mutation. The sync path only acquires the ``threading.RLock``.
    Because the sync path never tries to acquire the asyncio lock, there is
    no circular wait.

    The threading lock is reentrant — some paths may re-enter via
    ``move_pending_to_*`` wrappers.
    """

    def __init__(self) -> None:
        self._async_lock = asyncio.Lock()
        self._thread_lock = threading.RLock()
        self._pending: Dict[str, Any] = {}
        self._approved: Dict[str, Any] = {}
        self._rejected: Dict[str, Any] = {}
        self._modified: Dict[str, Any] = {}

    # --- sync API (Flask route handlers, WSGI threads) ------------------

    @contextmanager
    def _sync_section(self) -> Iterator[None]:
        """Acquire the threading lock for sync callers. Always use via ``with``."""
        self._thread_lock.acquire()
        try:
            yield
        finally:
            self._thread_lock.release()

    # pending ------------------------------------------------------------
    def put_pending(self, parser_id: str, value: Any) -> None:
        with self._sync_section():
            self._pending[parser_id] = value

    def get_pending(self, parser_id: str, default: Any = None) -> Any:
        with self._sync_section():
            return self._pending.get(parser_id, default)

    def pop_pending(self, parser_id: str, default: Any = None) -> Any:
        with self._sync_section():
            return self._pending.pop(parser_id, default)

    def contains_pending(self, parser_id: str) -> bool:
        with self._sync_section():
            return parser_id in self._pending

    def list_pending(self) -> List[Tuple[str, Any]]:
        with self._sync_section():
            return list(self._pending.items())

    def pending_count(self) -> int:
        with self._sync_section():
            return len(self._pending)

    # approved / rejected / modified -------------------------------------
    def put_approved(self, parser_id: str, value: Any) -> None:
        with self._sync_section():
            self._approved[parser_id] = value

    def put_rejected(self, parser_id: str, value: Any) -> None:
        with self._sync_section():
            self._rejected[parser_id] = value

    def put_modified(self, parser_id: str, value: Any) -> None:
        with self._sync_section():
            self._modified[parser_id] = value

    def list_approved(self) -> List[Tuple[str, Any]]:
        with self._sync_section():
            return list(self._approved.items())

    def list_rejected(self) -> List[Tuple[str, Any]]:
        with self._sync_section():
            return list(self._rejected.items())

    def list_modified(self) -> List[Tuple[str, Any]]:
        with self._sync_section():
            return list(self._modified.items())

    def approved_count(self) -> int:
        with self._sync_section():
            return len(self._approved)

    def rejected_count(self) -> int:
        with self._sync_section():
            return len(self._rejected)

    def modified_count(self) -> int:
        with self._sync_section():
            return len(self._modified)

    # multi-dict transactions --------------------------------------------
    def move_pending_to_approved(
        self, parser_id: str, *, overrides: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Atomic: pop from pending, apply overrides, push to approved."""
        with self._sync_section():
            item = self._pending.pop(parser_id, None)
            if item is None:
                return None
            if overrides and isinstance(item, dict):
                item.update(overrides)
            self._approved[parser_id] = item
            return item

    def move_pending_to_rejected(
        self, parser_id: str, *, reason: Optional[str] = None
    ) -> Any:
        with self._sync_section():
            item = self._pending.pop(parser_id, None)
            if item is None:
                return None
            if reason and isinstance(item, dict):
                item["rejection_reason"] = reason
            self._rejected[parser_id] = item
            return item

    def move_pending_to_modified(
        self, parser_id: str, *, modifications: Optional[Dict[str, Any]] = None
    ) -> Any:
        with self._sync_section():
            item = self._pending.pop(parser_id, None)
            if item is None:
                return None
            if modifications and isinstance(item, dict):
                item.update(modifications)
            self._modified[parser_id] = item
            return item

    # snapshot for external reads (metrics, legacy properties) -----------
    def snapshot(self) -> Dict[str, Dict[str, Any]]:
        """Return a shallow copy of all four dicts. Safe for external reads."""
        with self._sync_section():
            return {
                "pending": dict(self._pending),
                "approved": dict(self._approved),
                "rejected": dict(self._rejected),
                "modified": dict(self._modified),
            }

    # --- async API (conversion loop, feedback loop) ---------------------

    async def aput_pending(self, parser_id: str, value: Any) -> None:
        async with self._async_lock:
            with self._sync_section():
                self._pending[parser_id] = value

    async def aget_pending(self, parser_id: str, default: Any = None) -> Any:
        async with self._async_lock:
            with self._sync_section():
                return self._pending.get(parser_id, default)

    async def apop_pending(self, parser_id: str, default: Any = None) -> Any:
        async with self._async_lock:
            with self._sync_section():
                return self._pending.pop(parser_id, default)

    async def acontains_pending(self, parser_id: str) -> bool:
        async with self._async_lock:
            with self._sync_section():
                return parser_id in self._pending

    async def alist_pending(self) -> List[Tuple[str, Any]]:
        async with self._async_lock:
            with self._sync_section():
                return list(self._pending.items())

    async def apending_count(self) -> int:
        async with self._async_lock:
            with self._sync_section():
                return len(self._pending)

    async def aput_approved(self, parser_id: str, value: Any) -> None:
        async with self._async_lock:
            with self._sync_section():
                self._approved[parser_id] = value

    async def aput_rejected(self, parser_id: str, value: Any) -> None:
        async with self._async_lock:
            with self._sync_section():
                self._rejected[parser_id] = value

    async def aput_modified(self, parser_id: str, value: Any) -> None:
        async with self._async_lock:
            with self._sync_section():
                self._modified[parser_id] = value

    async def amove_pending_to_approved(
        self, parser_id: str, *, overrides: Optional[Dict[str, Any]] = None
    ) -> Any:
        async with self._async_lock:
            with self._sync_section():
                item = self._pending.pop(parser_id, None)
                if item is None:
                    return None
                if overrides and isinstance(item, dict):
                    item.update(overrides)
                self._approved[parser_id] = item
                return item

    async def amove_pending_to_rejected(
        self, parser_id: str, *, reason: Optional[str] = None
    ) -> Any:
        async with self._async_lock:
            with self._sync_section():
                item = self._pending.pop(parser_id, None)
                if item is None:
                    return None
                if reason and isinstance(item, dict):
                    item["rejection_reason"] = reason
                self._rejected[parser_id] = item
                return item

    async def amove_pending_to_modified(
        self, parser_id: str, *, modifications: Optional[Dict[str, Any]] = None
    ) -> Any:
        async with self._async_lock:
            with self._sync_section():
                item = self._pending.pop(parser_id, None)
                if item is None:
                    return None
                if modifications and isinstance(item, dict):
                    item.update(modifications)
                self._modified[parser_id] = item
                return item
