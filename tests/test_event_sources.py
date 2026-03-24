"""Unit tests for event sources."""

from __future__ import annotations

import asyncio
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from components.event_sources import (
    KafkaEventSource,
    SCOLAPISource,
    S3EventSource,
)
from services.event_normalizer import EventNormalizer


class TestEventNormalizer:
    """Test event normalization."""

    def test_normalize_event(self) -> None:
        """Test event normalization to common format."""
        event = {"alert_type": "DLP", "user": "john@example.com"}
        normalized = EventNormalizer.normalize(
            event,
            source_type="kafka",
            source_id="kafka-1",
            parser_id="netskope_dlp",
            original_format="json",
        )

        assert normalized["_metadata"]["source_type"] == "kafka"
        assert normalized["_metadata"]["source_id"] == "kafka-1"
        assert normalized["_metadata"]["parser_id"] == "netskope_dlp"
        assert normalized["_metadata"]["original_format"] == "json"
        assert "ingestion_time" in normalized["_metadata"]
        assert normalized["log"] == event

    def test_normalize_preserves_event_data(self) -> None:
        """Test that normalization preserves all event data."""
        event = {
            "field1": "value1",
            "field2": 123,
            "field3": {"nested": "value"},
            "field4": [1, 2, 3],
        }
        normalized = EventNormalizer.normalize(
            event,
            source_type="s3",
            source_id="s3-bucket-1",
            parser_id="generic_json",
        )

        assert normalized["log"] == event


class TestKafkaEventSource:
    """Test Kafka event source."""

    def test_kafka_source_initialization(self) -> None:
        """Test Kafka source initialization."""
        config = {
            "bootstrap_servers": "localhost:9092",
            "topics": ["test-topic"],
            "parser_id": "test-parser",
        }
        source = KafkaEventSource(config)

        assert source.source_type == "kafka"
        assert source.bootstrap_servers == "localhost:9092"
        assert source.topics == ["test-topic"]
        assert source.parser_id == "test-parser"

    def test_kafka_source_missing_required_config(self) -> None:
        """Test Kafka source validation of required config."""
        config = {
            "bootstrap_servers": "localhost:9092",
            # Missing topics and parser_id
        }
        with pytest.raises(ValueError):
            KafkaEventSource(config)

    def test_kafka_source_get_source_type(self) -> None:
        """Test source type identifier."""
        config = {
            "bootstrap_servers": "localhost:9092",
            "topics": ["test"],
            "parser_id": "test",
        }
        source = KafkaEventSource(config)
        assert source.get_source_type() == "kafka"


class TestSCOLAPISource:
    """Test SCOL API event source."""

    def test_scol_source_initialization(self) -> None:
        """Test SCOL API source initialization."""
        config = {
            "api_url": "https://api.example.com/events",
            "auth_token": "test-token",
            "checkpoint_key": "test_checkpoint",
            "parser_id": "test-parser",
        }
        source = SCOLAPISource(config)

        assert source.source_type == "scol"
        assert source.api_url == "https://api.example.com/events"
        assert source.auth_token == "test-token"
        assert source.parser_id == "test-parser"

    def test_scol_source_missing_required_config(self) -> None:
        """Test SCOL source validation of required config."""
        config = {
            "api_url": "https://api.example.com/events",
            # Missing auth_token, checkpoint_key, parser_id
        }
        with pytest.raises(ValueError):
            SCOLAPISource(config)

    def test_scol_extract_events_from_list(self) -> None:
        """Test extracting events from list response."""
        data = [
            {"event_id": 1, "type": "alert"},
            {"event_id": 2, "type": "alert"},
        ]
        events = SCOLAPISource._extract_events(data)
        assert len(events) == 2
        assert events == data

    def test_scol_extract_events_from_dict_with_events_key(self) -> None:
        """Test extracting events from dict with 'events' key."""
        data = {
            "events": [
                {"event_id": 1},
                {"event_id": 2},
            ],
            "total": 2,
        }
        events = SCOLAPISource._extract_events(data)
        assert len(events) == 2

    def test_scol_extract_events_from_single_event_dict(self) -> None:
        """Test extracting single event from dict."""
        data = {"event_id": 1, "timestamp": "2025-11-07T00:00:00Z"}
        events = SCOLAPISource._extract_events(data)
        assert len(events) == 1
        assert events[0] == data

    @pytest.mark.asyncio
    async def test_scol_checkpoint_store(self, tmp_path: Path) -> None:
        """Test checkpoint storage."""
        db_path = tmp_path / "test.db"
        from components.event_sources.scol_source import CheckpointStore

        store = CheckpointStore(str(db_path))

        # Test get non-existent checkpoint
        value = store.get_checkpoint("test_key")
        assert value is None

        # Test set and get checkpoint
        store.set_checkpoint("test_key", "test_value")
        value = store.get_checkpoint("test_key")
        assert value == "test_value"

        # Test update checkpoint
        store.set_checkpoint("test_key", "new_value")
        value = store.get_checkpoint("test_key")
        assert value == "new_value"


class TestS3EventSource:
    """Test S3 event source."""

    def test_s3_source_initialization(self) -> None:
        """Test S3 source initialization."""
        config = {
            "bucket": "test-bucket",
            "parser_id": "test-parser",
        }
        source = S3EventSource(config)

        assert source.source_type == "s3"
        assert source.bucket == "test-bucket"
        assert source.parser_id == "test-parser"

    def test_s3_source_missing_required_config(self) -> None:
        """Test S3 source validation."""
        config = {"bucket": "test-bucket"}  # Missing parser_id
        with pytest.raises(ValueError):
            S3EventSource(config)

    def test_s3_parse_jsonl(self) -> None:
        """Test parsing JSONL format."""
        from components.event_sources.s3_source import FileParser

        content = '{"id": 1, "event": "alert"}\n{"id": 2, "event": "warning"}'
        events = FileParser.parse_jsonl(content)

        assert len(events) == 2
        assert events[0]["id"] == 1
        assert events[1]["id"] == 2

    def test_s3_parse_json_list(self) -> None:
        """Test parsing JSON array format."""
        from components.event_sources.s3_source import FileParser

        content = '[{"id": 1}, {"id": 2}]'
        events = FileParser.parse_json(content)

        assert len(events) == 2

    def test_s3_parse_json_with_records_key(self) -> None:
        """Test parsing JSON with 'records' key."""
        from components.event_sources.s3_source import FileParser

        content = '{"records": [{"id": 1}, {"id": 2}], "count": 2}'
        events = FileParser.parse_json(content)

        assert len(events) == 2

    def test_s3_parse_csv(self) -> None:
        """Test parsing CSV format."""
        from components.event_sources.s3_source import FileParser

        content = "id,event\n1,alert\n2,warning"
        events = FileParser.parse_csv(content)

        assert len(events) == 2
        assert events[0]["id"] == "1"
        assert events[0]["event"] == "alert"


class TestBaseEventSource:
    """Test base event source functionality."""

    @pytest.mark.asyncio
    async def test_process_event_normalization(self) -> None:
        """Test event processing with normalization."""
        from components.event_sources.base_source import BaseEventSource

        class TestSource(BaseEventSource):
            def get_source_type(self) -> str:
                return "test"

            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

        config = {"source_id": "test-1"}
        source = TestSource(config)

        event = {"raw": "data"}
        normalized = await source.process_event(event, "test-parser")

        assert normalized["_metadata"]["source_type"] == "test"
        assert normalized["_metadata"]["source_id"] == "test-1"
        assert normalized["_metadata"]["parser_id"] == "test-parser"
        assert normalized["log"] == event
