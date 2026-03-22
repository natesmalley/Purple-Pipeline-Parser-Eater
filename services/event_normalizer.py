"""Event normalization for multi-source event ingestion."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict

logger = logging.getLogger(__name__)


class EventNormalizer:
    """Normalizes events from all sources to unified format."""

    @staticmethod
    def normalize(
        event: Dict[str, Any],
        source_type: str,
        source_id: str,
        parser_id: str,
        original_format: str = "json",
    ) -> Dict[str, Any]:
        """Normalize event to common format.

        All events are normalized to:
        {
          "_metadata": {
            "source_type": "kafka|scol|s3|azure|gcp|syslog",
            "source_id": "unique-identifier",
            "ingestion_time": "ISO-8601",
            "parser_id": "parser-to-use",
            "original_format": "json|syslog|csv"
          },
          "log": {
            // Original event (untouched)
          }
        }

        Args:
            event: Raw event data from source.
            source_type: Source type identifier.
            source_id: Source instance identifier.
            parser_id: Parser to apply to this event.
            original_format: Original format of event.

        Returns:
            Normalized event ready for message bus publication.
        """
        normalized = {
            "_metadata": {
                "source_type": source_type,
                "source_id": source_id,
                "ingestion_time": datetime.utcnow().isoformat() + "Z",
                "parser_id": parser_id,
                "original_format": original_format,
            },
            "log": event,
        }

        logger.debug(
            "Normalized event: source_type=%s, parser_id=%s",
            source_type,
            parser_id,
        )

        return normalized
