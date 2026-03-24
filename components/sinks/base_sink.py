"""Base class for output sinks."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class BaseSink(ABC):
    """Abstract base class for all output sinks."""

    @abstractmethod
    async def write_event(self, event: Dict[str, Any]) -> bool:
        """
        Write a single event to the sink.

        Args:
            event: OCSF event with metadata

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    async def write_events(self, events: List[Dict[str, Any]]) -> bool:
        """
        Write multiple events to the sink.

        Args:
            events: List of OCSF events with metadata

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    async def flush(self) -> bool:
        """
        Flush any buffered events to the sink.

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get sink statistics.

        Returns:
            Dictionary with statistics
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close the sink and release resources."""
        pass
