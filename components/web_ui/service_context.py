"""Stream A2.c — ServiceContext shim that satisfies the routes contract.

In the gunicorn/web process, ``ContinuousConversionService`` is NOT
constructed (it owns async loops, an event loop, an in-process queue —
none of which fit a sync WSGI worker). Instead, ``register_routes`` is
called with a ``ServiceContext`` that exposes the exact surface the routes
already consume:

- ``service.state`` -> ``StateStore`` (follower-mode in this process)
- ``service.get_status()`` -> 8-key payload mirroring
  ``ContinuousConversionService.get_status`` byte-for-byte
- ``service.get_runtime_status / request_runtime_reload / pop_runtime_reload
  / request_canary_promotion / pop_canary_promotion`` -> delegated to
  ``RuntimeProxy``

The web process never imports the daemon class; the daemon path keeps using
``ContinuousConversionService`` directly. There is no inheritance — the
contract is duck-typed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

from components.feedback_channel import FeedbackChannel
from components.runtime_proxy import RuntimeProxy
from components.state_store import StateStore


@dataclass
class ServiceContext:
    """Drop-in replacement for the ``service`` parameter to ``register_routes``."""

    state: StateStore
    config: Dict
    feedback_channel: FeedbackChannel
    runtime_proxy: RuntimeProxy
    output_dir: Optional[Path] = None

    def get_status(self) -> Dict:
        """Mirrors ``ContinuousConversionService.get_status`` byte-for-byte.

        Verified against ``continuous_conversion_service.py:622``. Drift here
        silently breaks ``/api/v1/status`` and the status dashboard.
        """
        return {
            "is_running": True,
            "pending_conversions": self.state.pending_count(),
            "approved_conversions": self.state.approved_count(),
            "rejected_conversions": self.state.rejected_count(),
            "modified_conversions": self.state.modified_count(),
            "queue_size": 0,
            "rag_status": {},
            "sdl_audit_stats": {},
        }

    # ---- runtime surface delegated to RuntimeProxy ----

    def get_runtime_status(self) -> Dict:
        return self.runtime_proxy.get_runtime_status()

    def request_runtime_reload(self, parser_id: str) -> bool:
        return self.runtime_proxy.request_runtime_reload(parser_id)

    def pop_runtime_reload(self, parser_id: str) -> Optional[str]:
        return self.runtime_proxy.pop_runtime_reload(parser_id)

    def request_canary_promotion(self, parser_id: str) -> bool:
        return self.runtime_proxy.request_canary_promotion(parser_id)

    def pop_canary_promotion(self, parser_id: str) -> Optional[str]:
        return self.runtime_proxy.pop_canary_promotion(parser_id)
