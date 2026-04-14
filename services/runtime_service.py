"""Runtime service orchestrating the complete transform pipeline.

Manages event consumption, transformation routing, metrics collection,
and error handling for the Agent 2 transform pipeline.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from collections import defaultdict

from components.message_bus_adapter import Message, create_bus_adapter
from components.manifest_store import ManifestStore
from components.canary_router import CanaryRouter
from components.transform_executor import create_executor
from components.runtime_metrics import RuntimeMetricsStore
from services.lua_code_cache import LuaCodeCache

logger = logging.getLogger(__name__)


class RuntimeService:
    """
    Orchestrates the complete transform pipeline.

    Responsibilities:
    - Consume normalized events from message bus
    - Route to appropriate parser based on manifest
    - Execute Lua transformations with canary support
    - Publish OCSF-compliant events
    - Collect performance metrics
    - Handle errors gracefully
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        """
        Initialize RuntimeService with configuration.

        Args:
            config: Configuration dictionary with keys:
                - message_bus: Bus configuration
                - executor: Executor configuration
                - manifest_directory: Path to manifest files
                - canary: Canary routing config
                - error_handling: Error handling config
        """
        self.config = config
        self.running = False

        # Initialize components
        self.bus = create_bus_adapter(config.get("message_bus", {}))
        self.executor = create_executor(config)

        manifest_dir = config.get("manifest_directory", "output")
        self.manifest_store = ManifestStore(base_output_dir=manifest_dir)

        canary_cfg = config.get("canary", {})
        self.canary_router = CanaryRouter(
            promotion_threshold=canary_cfg.get("promotion_threshold", 1000),
            error_tolerance=canary_cfg.get("error_tolerance", 0.01)
        )

        self.runtime_metrics = RuntimeMetricsStore()
        self.lua_cache = LuaCodeCache(max_size=config.get("lua_cache_size", 100))

        # Configuration
        self.input_topic = config.get("transform_worker", {}).get("input_topic", "raw-security-events")
        self.output_topic = config.get("transform_worker", {}).get("output_topic", "ocsf-events")

        # Statistics and state
        self.stats = {
            "total_events": 0,
            "successful_transforms": 0,
            "failed_transforms": 0,
            "parsers_active": set(),
            "startup_time": datetime.now(timezone.utc)
        }

        # Web UI integration state
        self.metrics: Dict[str, Dict[str, Any]] = {}
        self.reload_requests: Dict[str, str] = {}
        self.pending_promotions: Dict[str, str] = {}

        logger.info("RuntimeService initialized")

    async def start(self) -> None:
        """Start the runtime service and begin consuming events."""
        logger.info("=" * 70)
        logger.info("RuntimeService starting...")
        logger.info(f"Input topic: {self.input_topic}")
        logger.info(f"Output topic: {self.output_topic}")
        logger.info("=" * 70)

        self.running = True

        try:
            # Subscribe to input topic
            async for message in self.bus.subscribe(self.input_topic):
                if not self.running:
                    break
                await self._handle_message(message)

        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        except Exception as e:
            logger.error(f"Fatal error in RuntimeService: {e}", exc_info=True)
        finally:
            await self.stop()

    async def stop(self) -> None:
        """Stop the runtime service gracefully."""
        logger.info("Stopping RuntimeService...")
        self.running = False

        # Close executor
        await self.executor.close()

        # Close message bus
        await self.bus.close()

        # Log final statistics
        uptime = (datetime.now(timezone.utc) - self.stats["startup_time"]).total_seconds()
        logger.info("=" * 70)
        logger.info(f"Final statistics (uptime: {uptime:.1f}s):")
        logger.info(f"  Total events: {self.stats['total_events']}")
        logger.info(f"  Successful: {self.stats['successful_transforms']}")
        logger.info(f"  Failed: {self.stats['failed_transforms']}")
        if self.stats['total_events'] > 0:
            success_rate = (
                self.stats['successful_transforms'] / self.stats['total_events'] * 100
            )
            logger.info(f"  Success rate: {success_rate:.2f}%")
        logger.info(f"  Active parsers: {len(self.stats['parsers_active'])}")
        logger.info("=" * 70)

    async def _handle_message(self, message: Message) -> None:
        """
        Process a single message through the transform pipeline.

        Args:
            message: Message from bus with event data and headers
        """
        start_time = datetime.now(timezone.utc)
        parser_id = message.headers.get("parser_id", "unknown")
        event = message.value

        self.stats["total_events"] += 1
        self.stats["parsers_active"].add(parser_id)

        try:
            # Load manifest
            manifest = self.manifest_store.load_manifest(parser_id, "stable")
            canary_manifest = self.manifest_store.load_manifest(parser_id, "canary")

            # Register with canary router
            self.canary_router.register(parser_id, manifest, "stable")
            self.canary_router.register(parser_id, canary_manifest, "canary")

            # Select version (stable or canary)
            version_mode, selected_manifest = self.canary_router.select(
                parser_id,
                hash(event.get("id", parser_id))
            )
            is_canary = version_mode == "canary"

            # Load Lua code
            lua_filename = (
                selected_manifest.lua_metadata.file
                if selected_manifest.lua_metadata
                else "transform.lua"
            )
            lua_code = self.manifest_store.load_lua(parser_id, lua_filename)

            if not lua_code:
                raise ValueError(f"Lua code not found for {parser_id}")

            # Execute transformation
            success, result = await self.executor.execute(lua_code, event, parser_id)

            # Record metrics
            self.canary_router.record(
                parser_id,
                selected_manifest.version.semantic,
                success,
                is_canary,
                result.get("error") if not success else None
            )

            runtime_metric = self.runtime_metrics.for_parser(parser_id)
            runtime_metric.record(success, is_canary, result.get("error") if not success else None)
            self.update_metrics({parser_id: runtime_metric.to_dict()})

            if not success:
                self.stats["failed_transforms"] += 1
                logger.error(f"Transform failed for {parser_id}: {result.get('error')}")
                await self._handle_transform_error(event, parser_id, result.get("error"))
                return

            self.stats["successful_transforms"] += 1

            # Build output event with metadata
            execution_time_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

            output_event = {
                "_metadata": {
                    **message.headers,
                    "parser_version": selected_manifest.version.semantic,
                    "transform_time": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "execution_time_ms": round(execution_time_ms, 2),
                    "canary_used": is_canary
                },
                "log": result
            }

            # Publish to output topic
            await self.bus.publish(
                self.output_topic,
                Message(value=output_event, headers={"parser_id": parser_id})
            )

            logger.debug(
                f"Transformed event with {parser_id} "
                f"(canary={is_canary}, latency={execution_time_ms:.2f}ms)"
            )

            # Check for canary promotion
            if self.pending_promotions.get(parser_id) == "pending":
                if self.canary_router.should_promote_canary(parser_id):
                    self.pending_promotions[parser_id] = "ready"
                    logger.info(f"Canary promotion ready for {parser_id}")

        except (KeyError, ValueError) as e:
            self.stats["failed_transforms"] += 1
            logger.error(f"No manifest available for {parser_id}: {e}")
            await self._handle_transform_error(event, parser_id, str(e))

        except Exception as e:
            self.stats["failed_transforms"] += 1
            logger.error(f"Unexpected error processing {parser_id}: {e}", exc_info=True)
            await self._handle_transform_error(event, parser_id, str(e))

    async def _handle_transform_error(
        self,
        event: Dict[str, Any],
        parser_id: str,
        error: str
    ) -> None:
        """
        Handle transformation errors.

        Args:
            event: Original event
            parser_id: Parser ID
            error: Error message
        """
        error_config = self.config.get("error_handling", {})

        if error_config.get("dlq_enabled"):
            dlq_topic = error_config.get("dlq_topic", "transform-errors")

            try:
                error_event = {
                    **event,
                    "_error": {
                        "parser_id": parser_id,
                        "error": error,
                        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                    }
                }

                await self.bus.publish(
                    dlq_topic,
                    Message(value=error_event, headers={"parser_id": parser_id, "error": error})
                )
                logger.info(f"Published error event to DLQ: {dlq_topic}")

            except Exception as dlq_error:
                logger.error(f"Failed to publish to DLQ: {dlq_error}")

    def get_runtime_status(self) -> Dict:
        """Get overall runtime status."""
        uptime = (datetime.now(timezone.utc) - self.stats["startup_time"]).total_seconds()

        return {
            "running": self.running,
            "uptime_seconds": uptime,
            "metrics": self.metrics,
            "reload_requests": self.reload_requests,
            "pending_promotions": self.pending_promotions,
            "stats": {
                "total_events": self.stats["total_events"],
                "successful": self.stats["successful_transforms"],
                "failed": self.stats["failed_transforms"],
                "success_rate": (
                    self.stats["successful_transforms"] / self.stats["total_events"]
                    if self.stats["total_events"] > 0
                    else 0
                ),
                "active_parsers": len(self.stats["parsers_active"]),
                "parsers": list(self.stats["parsers_active"])
            }
        }

    def update_metrics(self, data: Dict[str, Any]) -> None:
        """Update runtime metrics (for web UI integration)."""
        for parser_id, metrics in data.items():
            if metrics is not None:
                self.metrics[parser_id] = metrics

    def request_runtime_reload(self, parser_id: str) -> bool:
        """Request runtime reload for a parser."""
        self.reload_requests[parser_id] = "pending"
        logger.info(f"Reload requested for {parser_id}")
        return True

    def pop_reload_request(self, parser_id: str) -> Optional[str]:
        """Pop a reload request."""
        return self.reload_requests.pop(parser_id, None)

    def request_canary_promotion(self, parser_id: str) -> bool:
        """Request canary promotion for a parser."""
        self.pending_promotions[parser_id] = "pending"
        logger.info(f"Canary promotion requested for {parser_id}")
        return True

    def pop_canary_promotion(self, parser_id: str) -> Optional[str]:
        """Pop a canary promotion request."""
        return self.pending_promotions.pop(parser_id, None)

    def get_statistics(self) -> Dict[str, Any]:
        """Get detailed statistics."""
        return self.get_runtime_status()

