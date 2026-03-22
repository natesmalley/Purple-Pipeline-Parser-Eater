"""Kafka consumer event source."""

from __future__ import annotations

import json
import logging
from typing import Any, Awaitable, Callable, Dict, List

from .base_source import BaseEventSource

logger = logging.getLogger(__name__)


class KafkaEventSource(BaseEventSource):
    """Consume events from Kafka topics.

    Features:
    - Multi-topic subscription
    - Consumer group management
    - Offset tracking
    - Batch consumption
    - Auto-commit or manual commit
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize Kafka consumer.

        Args:
            config: Configuration with keys:
                - bootstrap_servers: Kafka broker addresses
                - topics: List of topics to consume
                - consumer_group: Consumer group name
                - batch_size: Events per batch (default 100)
                - parser_id: Parser to apply to events
        """
        super().__init__(config)
        self.validate_config(["bootstrap_servers", "topics", "parser_id"])

        self.bootstrap_servers = config["bootstrap_servers"]
        self.topics = config["topics"]
        self.consumer_group = config.get("consumer_group", "pppe-ingest")
        self.batch_size = config.get("batch_size", 100)
        self.parser_id = config["parser_id"]
        self.auto_offset_reset = config.get("auto_offset_reset", "earliest")
        self.enable_auto_commit = config.get("enable_auto_commit", True)

        self._consumer = None
        self._callback = None

    def get_source_type(self) -> str:
        """Return source type identifier."""
        return "kafka"

    async def start(self) -> None:
        """Start consuming from Kafka topics."""
        try:
            from aiokafka import AIOKafkaConsumer  # type: ignore
        except ImportError as e:
            raise ImportError("aiokafka not installed. Install with: pip install aiokafka") from e

        try:
            self._consumer = AIOKafkaConsumer(
                *self.topics,
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.consumer_group,
                auto_offset_reset=self.auto_offset_reset,
                enable_auto_commit=self.enable_auto_commit,
                value_deserializer=lambda m: json.loads(m.decode("utf-8")) if m else None,
            )

            await self._consumer.start()
            logger.info(
                "Kafka consumer started for topics: %s (group: %s)",
                self.topics,
                self.consumer_group,
            )

            # Start consuming in the background
            if self._callback:
                await self._consume_with_callback()

        except Exception as e:
            logger.error("Failed to start Kafka consumer: %s", e)
            raise

    async def stop(self) -> None:
        """Stop Kafka consumer and cleanup."""
        if self._consumer:
            await self._consumer.stop()
            logger.info("Kafka consumer stopped")

    def set_event_callback(self, callback) -> None:
        """Set callback function for consumed events.

        Args:
            callback: Async callable(event, parser_id) that processes events.
        """
        self._callback = callback

    async def consume_batch(self) -> List[Dict[str, Any]]:
        """Consume a batch of events from Kafka.

        Returns:
            List of consumed events.
        """
        if not self._consumer:
            raise RuntimeError("Consumer not started")

        events = []
        try:
            async for msg in self._consumer:
                if msg.value:
                    events.append(msg.value)
                if len(events) >= self.batch_size:
                    break
        except Exception as e:
            logger.error("Error consuming from Kafka: %s", e)

        return events

    async def _consume_with_callback(self) -> None:
        """Consume events and call callback for each."""
        if not self._consumer or not self._callback:
            return

        try:
            async for msg in self._consumer:
                if msg.value:
                    await self._callback(msg.value, self.parser_id)
        except Exception as e:
            logger.error("Error in Kafka consumption loop: %s", e)
