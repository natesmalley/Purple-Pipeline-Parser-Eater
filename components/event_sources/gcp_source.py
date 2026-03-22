"""Google Cloud Pub/Sub consumer source."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Optional

from .base_source import BaseEventSource

logger = logging.getLogger(__name__)


class GCPPubSubSource(BaseEventSource):
    """Google Cloud Pub/Sub consumer.

    Features:
    - Multiple subscription consumers
    - Acknowledgment handling
    - Service account authentication
    - Flow control (max messages)
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize GCP Pub/Sub source.

        Args:
            config: Configuration with keys:
                - project_id: GCP project ID
                - subscription_id: Pub/Sub subscription ID
                - credentials_file: Path to service account JSON file
                - max_messages: Max concurrent messages (default 100)
                - parser_id: Parser to apply to events
        """
        super().__init__(config)
        self.validate_config([
            "project_id",
            "subscription_id",
            "credentials_file",
            "parser_id",
        ])

        self.project_id = config["project_id"]
        self.subscription_id = config["subscription_id"]
        self.credentials_file = config["credentials_file"]
        self.max_messages = config.get("max_messages", 100)
        self.parser_id = config["parser_id"]

        self._subscriber = None
        self._callback = None
        self._subscription_path = None
        self._streaming_pull_future = None

    def get_source_type(self) -> str:
        """Return source type identifier."""
        return "gcp"

    async def start(self) -> None:
        """Start consuming from Pub/Sub."""
        try:
            from google.cloud import pubsub_v1  # type: ignore
        except ImportError as e:
            raise ImportError(
                "Google Cloud SDK not installed. "
                "Install with: pip install google-cloud-pubsub"
            ) from e

        try:
            self._subscriber = pubsub_v1.SubscriberClient.from_service_account_file(
                self.credentials_file
            )

            self._subscription_path = self._subscriber.subscription_path(
                self.project_id,
                self.subscription_id,
            )

            logger.info(
                "GCP Pub/Sub subscriber started for %s/%s",
                self.project_id,
                self.subscription_id,
            )

            if self._callback:
                await self._consume_with_callback()

        except Exception as e:
            logger.error("Failed to start GCP Pub/Sub subscriber: %s", e)
            raise

    async def stop(self) -> None:
        """Stop Pub/Sub subscriber."""
        if self._streaming_pull_future:
            self._streaming_pull_future.cancel()
            logger.info("GCP Pub/Sub subscriber stopped")

    def set_event_callback(self, callback) -> None:
        """Set callback function for received messages.

        Args:
            callback: Async callable(event, parser_id) that processes events.
        """
        self._callback = callback

    async def _consume_with_callback(self) -> None:
        """Consume messages and call callback for each."""
        if not self._subscriber or not self._callback or not self._subscription_path:
            return

        def message_callback(message) -> None:
            """Handle received message."""
            try:
                # Decode message data
                message_data = message.data.decode("utf-8")
                event = json.loads(message_data)

                # Schedule callback execution
                asyncio.create_task(self._callback(event, self.parser_id))

                # Acknowledge the message
                message.ack()

            except Exception as e:
                logger.error("Error processing Pub/Sub message: %s", e)
                # Negative acknowledge on error
                message.nack()

        try:
            flow_control = pubsub_v1.types.FlowControl(
                max_messages=self.max_messages,
                max_bytes=1000 * 1024 * 1024,  # 1GB
            )

            self._streaming_pull_future = self._subscriber.subscribe(
                self._subscription_path,
                callback=message_callback,
                flow_control=flow_control,
            )

            logger.info("Pub/Sub streaming pull started")

            # Keep subscription alive
            try:
                self._streaming_pull_future.result()
            except Exception as e:
                logger.error("Pub/Sub streaming error: %s", e)

        except Exception as e:
            logger.error("Error in Pub/Sub consumption: %s", e)
