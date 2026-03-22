"""Azure Event Hubs consumer source."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Awaitable, Callable, Dict, Optional

from .base_source import BaseEventSource

logger = logging.getLogger(__name__)


class AzureEventHubsSource(BaseEventSource):
    """Azure Event Hubs consumer.

    Features:
    - Multiple Event Hub consumers
    - Checkpoint storage in Azure Blob Storage
    - Consumer groups
    - Partition management
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize Azure Event Hubs source.

        Args:
            config: Configuration with keys:
                - connection_string: Event Hub connection string
                - event_hub_name: Event Hub name
                - consumer_group: Consumer group (default $Default)
                - checkpoint_store_connection: Azure Storage connection string
                - parser_id: Parser to apply to events
        """
        super().__init__(config)
        self.validate_config([
            "connection_string",
            "event_hub_name",
            "checkpoint_store_connection",
            "parser_id",
        ])

        self.connection_string = config["connection_string"]
        self.event_hub_name = config["event_hub_name"]
        self.consumer_group = config.get("consumer_group", "$Default")
        self.checkpoint_store_connection = config["checkpoint_store_connection"]
        self.parser_id = config["parser_id"]

        self._client = None
        self._callback = None

    def get_source_type(self) -> str:
        """Return source type identifier."""
        return "azure"

    async def start(self) -> None:
        """Start consuming from Event Hub."""
        try:
            from azure.eventhub.aio import EventHubConsumerClient  # type: ignore
            from azure.eventhub.extensions.checkpointstoreblobaio import (  # type: ignore
                BlobCheckpointStore,
            )
        except ImportError as e:
            raise ImportError(
                "Azure SDK not installed. "
                "Install with: pip install azure-eventhub azure-eventhub-checkpointstoreblob-aio"
            ) from e

        try:
            checkpoint_store = BlobCheckpointStore.from_connection_string(
                self.checkpoint_store_connection,
                container_name="eventhub-checkpoints",
            )

            self._client = EventHubConsumerClient.from_connection_string(
                self.connection_string,
                consumer_group=self.consumer_group,
                eventhub_name=self.event_hub_name,
                checkpoint_store=checkpoint_store,
            )

            logger.info(
                "Azure Event Hub consumer started for %s (group: %s)",
                self.event_hub_name,
                self.consumer_group,
            )

            if self._callback:
                await self._consume_with_callback()

        except Exception as e:
            logger.error("Failed to start Azure Event Hub consumer: %s", e)
            raise

    async def stop(self) -> None:
        """Stop Event Hub consumer."""
        if self._client:
            await self._client.close()
            logger.info("Azure Event Hub consumer stopped")

    def set_event_callback(
        self, callback: Callable[[Dict[str, Any], str], Awaitable[None]]
    ) -> None:
        """Set callback function for received events.

        Args:
            callback: Async callable(event, parser_id) that processes events.
        """
        self._callback = callback

    async def _consume_with_callback(self) -> None:
        """Consume events and call callback for each."""
        if not self._client or not self._callback:
            return

        def on_event(partition_context, event) -> None:
            """Handle received event."""
            try:
                # Convert event to dict
                event_data = event.get_body()
                if isinstance(event_data, bytes):
                    event_dict = json.loads(event_data.decode("utf-8"))
                else:
                    event_dict = event_data

                # Schedule async callback execution
                asyncio.create_task(
                    self._callback(event_dict, self.parser_id)
                )

            except Exception as e:
                logger.error("Error processing event: %s", e)

        try:
            async with self._client:
                await self._client.receive(
                    on_event=on_event,
                    on_error=self._on_error,
                )
        except Exception as e:
            logger.error("Error in Event Hub consumption loop: %s", e)

    def _on_error(self, partition_context, error) -> None:
        """Handle consumption error.

        Args:
            partition_context: Partition context.
            error: Error that occurred.
        """
        logger.error(
            "Error in partition %s: %s",
            partition_context.partition_id if partition_context else "unknown",
            error,
        )
