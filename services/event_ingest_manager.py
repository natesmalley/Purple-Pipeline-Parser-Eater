"""Event ingestion manager orchestrating all event sources."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from components.event_sources import (
    AzureEventHubsSource,
    GCPPubSubSource,
    KafkaEventSource,
    S3EventSource,
    SCOLAPISource,
    SyslogHECSource,
    BaseEventSource,
)
from components.message_bus_adapter import Message, create_bus_adapter
from .event_normalizer import EventNormalizer

logger = logging.getLogger(__name__)


class IngestionMetrics:
    """Track event ingestion metrics."""

    def __init__(self) -> None:
        """Initialize metrics tracker."""
        self.events_processed = 0
        self.events_by_source: Dict[str, int] = {}
        self.events_by_parser: Dict[str, int] = {}
        self.errors = 0

    def record_event(self, source_type: str, parser_id: str) -> None:
        """Record processed event.

        Args:
            source_type: Source type that produced event.
            parser_id: Parser applied to event.
        """
        self.events_processed += 1
        self.events_by_source[source_type] = self.events_by_source.get(source_type, 0) + 1
        self.events_by_parser[parser_id] = self.events_by_parser.get(parser_id, 0) + 1

    def record_error(self) -> None:
        """Record processing error."""
        self.errors += 1

    def get_stats(self) -> Dict[str, Any]:
        """Get current metrics.

        Returns:
            Dictionary of metrics.
        """
        return {
            "events_processed": self.events_processed,
            "events_by_source": self.events_by_source.copy(),
            "events_by_parser": self.events_by_parser.copy(),
            "errors": self.errors,
        }


class EventIngestManager:
    """Manages all event sources and coordinates ingestion.

    Features:
    - Start/stop all sources
    - Route events to message bus
    - Monitor ingestion metrics
    - Handle source failures gracefully
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize event ingestion manager.

        Args:
            config: Configuration dictionary with:
                - message_bus: Message bus configuration
                - kafka: Kafka source config (optional)
                - scol_api: SCOL API source config (optional)
                - s3: S3 source config (optional)
                - azure: Azure Event Hubs config (optional)
                - gcp: GCP Pub/Sub config (optional)
                - syslog_hec: Syslog HEC config (optional)
        """
        self.config = config
        self.sources: List[BaseEventSource] = []
        self.message_bus = None
        self.metrics = IngestionMetrics()
        self._tasks: List[asyncio.Task] = []

    async def initialize(self) -> None:
        """Initialize all enabled sources."""
        logger.info("Initializing event ingestion manager")

        # Create message bus adapter
        self.message_bus = create_bus_adapter(self.config.get("message_bus", {}))
        logger.info("Message bus initialized")

        # Initialize Kafka source
        if self.config.get("kafka", {}).get("enabled"):
            try:
                kafka_config = self.config["kafka"]
                kafka_config["source_id"] = kafka_config.get("source_id", "kafka-default")
                source = KafkaEventSource(kafka_config)
                source.set_event_callback(self.process_event)
                self.sources.append(source)
                logger.info("Kafka source initialized")
            except Exception as e:
                logger.error("Failed to initialize Kafka source: %s", e)

        # Initialize SCOL API sources
        if self.config.get("scol_api", {}).get("enabled"):
            try:
                scol_config = self.config["scol_api"]
                for source_config in scol_config.get("sources", []):
                    source_config["checkpoint_db"] = scol_config.get(
                        "checkpoint_db",
                        "data/scol_checkpoints.db",
                    )
                    source = SCOLAPISource(source_config)
                    source.set_event_callback(self.process_event)
                    self.sources.append(source)
                logger.info("SCOL API sources initialized")
            except Exception as e:
                logger.error("Failed to initialize SCOL API sources: %s", e)

        # Initialize S3 source
        if self.config.get("s3", {}).get("enabled"):
            try:
                s3_config = self.config["s3"]
                for bucket_config in s3_config.get("buckets", []):
                    source = S3EventSource(bucket_config)
                    source.set_event_callback(self.process_event)
                    self.sources.append(source)
                logger.info("S3 sources initialized")
            except Exception as e:
                logger.error("Failed to initialize S3 sources: %s", e)

        # Initialize Azure Event Hubs source
        if self.config.get("azure", {}).get("enabled"):
            try:
                azure_config = self.config["azure"]
                for hub_config in azure_config.get("event_hubs", []):
                    source = AzureEventHubsSource(hub_config)
                    source.set_event_callback(self.process_event)
                    self.sources.append(source)
                logger.info("Azure Event Hubs sources initialized")
            except Exception as e:
                logger.error("Failed to initialize Azure Event Hubs sources: %s", e)

        # Initialize GCP Pub/Sub source
        if self.config.get("gcp", {}).get("enabled"):
            try:
                gcp_config = self.config["gcp"]
                for sub_config in gcp_config.get("subscriptions", []):
                    source = GCPPubSubSource(sub_config)
                    source.set_event_callback(self.process_event)
                    self.sources.append(source)
                logger.info("GCP Pub/Sub sources initialized")
            except Exception as e:
                logger.error("Failed to initialize GCP Pub/Sub sources: %s", e)

        # Initialize Syslog HEC source
        if self.config.get("syslog_hec", {}).get("enabled"):
            try:
                hec_config = self.config["syslog_hec"]
                source = SyslogHECSource(hec_config)
                source.set_event_callback(self.process_event)
                self.sources.append(source)
                logger.info("Syslog HEC receiver initialized")
            except Exception as e:
                logger.error("Failed to initialize Syslog HEC receiver: %s", e)

        logger.info("Event ingestion manager initialized with %d sources", len(self.sources))

    async def start(self) -> None:
        """Start all event sources."""
        if not self.sources:
            raise RuntimeError("No sources initialized")

        logger.info("Starting %d event sources", len(self.sources))

        tasks = [source.start() for source in self.sources]
        self._tasks = await asyncio.gather(*[asyncio.create_task(t) for t in tasks],
                                          return_exceptions=True)

        # Check for errors
        for i, result in enumerate(self._tasks):
            if isinstance(result, Exception):
                logger.error("Source %d failed to start: %s", i, result)

        logger.info("All event sources started")

    async def process_event(
        self,
        event: Dict[str, Any],
        parser_id: str,
    ) -> None:
        """Process and publish event to message bus.

        Args:
            event: Raw event data.
            parser_id: Parser ID for this event.
        """
        try:
            # Normalize event
            normalized = EventNormalizer.normalize(
                event,
                source_type="unknown",
                source_id="unknown",
                parser_id=parser_id,
            )

            # Publish to message bus
            output_topic = self.config.get("message_bus", {}).get(
                "output_topic",
                "raw-security-events",
            )
            message = Message(value=normalized, headers={})
            await self.message_bus.publish(output_topic, message)

            # Update metrics
            self.metrics.record_event("unknown", parser_id)

        except Exception as e:
            logger.error("Error processing event: %s", e)
            self.metrics.record_error()

    async def stop(self) -> None:
        """Graceful shutdown of all sources."""
        logger.info("Stopping event ingestion manager")

        # Stop all sources
        tasks = [source.stop() for source in self.sources]
        await asyncio.gather(*tasks, return_exceptions=True)

        # Close message bus
        if self.message_bus:
            await self.message_bus.close()

        logger.info("Event ingestion manager stopped")

    def get_metrics(self) -> Dict[str, Any]:
        """Get current ingestion metrics.

        Returns:
            Dictionary of metrics.
        """
        return self.metrics.get_stats()
