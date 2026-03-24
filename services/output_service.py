"""Output service for event delivery to multiple sinks."""

import asyncio
import logging
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from components.message_bus_adapter import create_bus_adapter, MessageBusAdapter
from components.observo_ingest_client import ObservoIngestClient
from components.output_validator import OutputValidator
from components.sinks.s3_archive_sink import S3ArchiveSink

logger = logging.getLogger(__name__)


class OutputService:
    """
    Main output service that:
    - Consumes OCSF events from Agent 2
    - Validates OCSF compliance
    - Delivers to multiple sinks (Observo, S3, etc.)
    - Tracks delivery status
    - Handles retries and errors
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize output service.

        Args:
            config: Configuration dictionary with message_bus, validator,
                   sinks, and retry settings
        """
        self.config = config
        self.running = False

        self.message_bus: Optional[MessageBusAdapter] = None
        self.validator = OutputValidator(
            strict_mode=config.get("validator", {}).get("strict_mode", False)
        )

        self.sinks: Dict[str, Any] = {}
        self._initialize_sinks()

        self.stats = {
            "total_received": 0,
            "validation_passed": 0,
            "validation_failed": 0,
            "delivery_success": 0,
            "delivery_failed": 0,
            "by_sink": defaultdict(
                lambda: {
                    "success": 0,
                    "failed": 0,
                    "latency_ms": [],
                }
            ),
        }

        logger.info("OutputService initialized")

    def _initialize_sinks(self) -> None:
        """Initialize configured sinks."""
        sinks_config = self.config.get("sinks", {})

        if sinks_config.get("observo", {}).get("enabled"):
            observo_cfg = sinks_config["observo"]
            self.sinks["observo"] = ObservoIngestClient(
                base_url=observo_cfg["base_url"],
                api_token=observo_cfg["api_token"],
                max_batch_size=observo_cfg.get("batch_size", 100),
            )
            logger.info("Observo.ai sink enabled")

        if sinks_config.get("s3_archive", {}).get("enabled"):
            s3_cfg = sinks_config["s3_archive"]
            self.sinks["s3_archive"] = S3ArchiveSink(
                bucket_name=s3_cfg["bucket"],
                prefix=s3_cfg.get("prefix", "purple-pipeline"),
                batch_size=s3_cfg.get("batch_size", 1000),
            )
            logger.info(f"S3 archive sink enabled: s3://{s3_cfg['bucket']}")

    async def start(self) -> None:
        """Start the output service."""
        logger.info("Starting OutputService...")
        self.running = True

        self.message_bus = create_bus_adapter(self.config["message_bus"])

        input_topic = self.config["message_bus"]["input_topic"]
        logger.info(f"OutputService started, consuming from '{input_topic}'")

        await self._test_connections()

        try:
            async for message in self.message_bus.subscribe(input_topic):
                if not self.running:
                    break
                event = message.value
                await self._process_event(event)
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        finally:
            await self.stop()

    async def stop(self) -> None:
        """Stop the output service gracefully."""
        logger.info("Stopping OutputService...")
        self.running = False

        if "s3_archive" in self.sinks:
            await self.sinks["s3_archive"].flush()

        if self.message_bus:
            await self.message_bus.close()

        if "observo" in self.sinks:
            await self.sinks["observo"].close()

        for sink_name, sink in self.sinks.items():
            if hasattr(sink, "close"):
                try:
                    await sink.close()
                except Exception as e:
                    logger.warning(f"Error closing {sink_name}: {e}")

        logger.info(f"Final statistics: {self.get_statistics()}")

    async def _test_connections(self) -> None:
        """Test connections to all sinks."""
        logger.info("Testing sink connections...")

        if "observo" in self.sinks:
            observo_ok = await self.sinks["observo"].test_connection()
            if observo_ok:
                logger.info("✓ Observo.ai connection successful")
            else:
                logger.warning("✗ Observo.ai connection test inconclusive")

    async def _process_event(self, event: Dict[str, Any]) -> None:
        """
        Process a single OCSF event through output pipeline.

        Args:
            event: OCSF event from Agent 2 with structure:
                {
                    "_metadata": {...},
                    "log": { OCSF event }
                }
        """
        start_time = datetime.utcnow()
        self.stats["total_received"] += 1

        try:
            metadata = event.get("_metadata", {})
            ocsf_log = event.get("log", {})

            if not ocsf_log:
                raise ValueError("Event missing 'log' field")

            is_valid = self.validator.validate_ocsf(ocsf_log)

            if not is_valid:
                self.stats["validation_failed"] += 1
                logger.warning(
                    f"Event validation failed for parser: "
                    f"{metadata.get('parser_id', 'unknown')}"
                )
                return

            self.stats["validation_passed"] += 1

            delivery_tasks = []

            for sink_name, sink in self.sinks.items():
                task = self._deliver_to_sink(sink_name, sink, event)
                delivery_tasks.append(task)

            results = await asyncio.gather(
                *delivery_tasks, return_exceptions=True
            )

            success_count = sum(1 for r in results if r is True)
            failed_count = len(results) - success_count

            if success_count > 0:
                self.stats["delivery_success"] += 1
            if failed_count > 0:
                self.stats["delivery_failed"] += 1

            latency_ms = (
                (datetime.utcnow() - start_time).total_seconds() * 1000
            )
            logger.debug(
                f"Event processed: {success_count} sinks succeeded, "
                f"{failed_count} failed (latency={latency_ms:.2f}ms)"
            )

        except Exception as e:
            logger.error(f"Error processing event: {e}", exc_info=True)
            self.stats["delivery_failed"] += 1

    async def _deliver_to_sink(
        self,
        sink_name: str,
        sink: Any,
        event: Dict[str, Any],
    ) -> bool:
        """
        Deliver event to a specific sink with retry logic.

        Args:
            sink_name: Name of sink
            sink: Sink instance
            event: Full event with metadata

        Returns:
            True if successful, False if failed after retries
        """
        retry_config = self.config.get("retry", {})
        max_attempts = retry_config.get("max_attempts", 5)
        base_backoff = retry_config.get("base_backoff_seconds", 2)
        max_backoff = retry_config.get("max_backoff_seconds", 60)

        start_time = datetime.utcnow()

        for attempt in range(1, max_attempts + 1):
            try:
                if isinstance(sink, ObservoIngestClient):
                    result = await sink.ingest_events([event])
                    success = result.get("accepted", 0) > 0

                elif isinstance(sink, S3ArchiveSink):
                    success = await sink.write_event(event)

                else:
                    logger.warning(f"Unknown sink type: {type(sink)}")
                    success = False

                if success:
                    latency_ms = (
                        (datetime.utcnow() - start_time).total_seconds()
                        * 1000
                    )
                    self.stats["by_sink"][sink_name]["success"] += 1
                    self.stats["by_sink"][sink_name]["latency_ms"].append(
                        latency_ms
                    )

                    logger.debug(
                        f"Delivered to {sink_name} "
                        f"(attempt {attempt}, latency={latency_ms:.2f}ms)"
                    )
                    return True
                else:
                    raise Exception("Delivery returned failure status")

            except Exception as e:
                logger.warning(
                    f"Delivery to {sink_name} failed "
                    f"(attempt {attempt}/{max_attempts}): {e}"
                )

                if attempt < max_attempts:
                    backoff = min(
                        base_backoff * (2 ** (attempt - 1)), max_backoff
                    )
                    logger.info(f"Retrying in {backoff}s...")
                    await asyncio.sleep(backoff)
                else:
                    self.stats["by_sink"][sink_name]["failed"] += 1
                    logger.error(
                        f"Delivery to {sink_name} failed after "
                        f"{max_attempts} attempts"
                    )
                    return False

        return False

    def get_statistics(self) -> Dict[str, Any]:
        """Get output service statistics."""
        stats = dict(self.stats)

        for sink_name, sink_stats in stats["by_sink"].items():
            latencies = sink_stats["latency_ms"]
            if latencies:
                sink_stats["avg_latency_ms"] = sum(latencies) / len(
                    latencies
                )
                sink_stats["max_latency_ms"] = max(latencies)
                del sink_stats["latency_ms"]

        return stats
