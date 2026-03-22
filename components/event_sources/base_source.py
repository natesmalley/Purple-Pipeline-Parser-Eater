"""Abstract base class for event sources."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class BaseEventSource(ABC):
    """Abstract base class for all event sources."""

    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize event source with configuration.

        Args:
            config: Source-specific configuration dictionary.
        """
        self.config = config
        self.source_type = self.get_source_type()
        self.source_id = config.get("source_id", self.__class__.__name__)

    @abstractmethod
    def get_source_type(self) -> str:
        """Return the source type identifier (e.g., 'kafka', 'scol', 's3')."""

    @abstractmethod
    async def start(self) -> None:
        """Start the event source.

        For pull-based sources (Kafka, API polling), this begins consuming.
        For push-based sources (HEC), this starts the server.
        """

    @abstractmethod
    async def stop(self) -> None:
        """Stop the event source and clean up resources."""

    async def process_event(
        self,
        event: Dict[str, Any],
        parser_id: str,
        original_format: str = "json",
    ) -> Dict[str, Any]:
        """Process a raw event into normalized format.

        Args:
            event: Raw event data from source.
            parser_id: Parser ID to apply to this event.
            original_format: Format of original event (json, syslog, csv).

        Returns:
            Event in normalized format ready for message bus.
        """
        from ..event_normalizer import EventNormalizer

        return EventNormalizer.normalize(
            event,
            source_type=self.source_type,
            source_id=self.source_id,
            parser_id=parser_id,
            original_format=original_format,
        )

    def validate_config(self, required_keys: List[str]) -> None:
        """Validate that required configuration keys are present.

        Args:
            required_keys: List of required configuration keys.

        Raises:
            ValueError: If any required key is missing.
        """
        missing = [key for key in required_keys if key not in self.config]
        if missing:
            raise ValueError(f"Missing required config keys: {missing}")
