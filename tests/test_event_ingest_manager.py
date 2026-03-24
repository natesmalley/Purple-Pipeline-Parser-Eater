"""Integration tests for event ingest manager."""

from __future__ import annotations

import asyncio
import pytest
from typing import Dict, Any

from services.event_ingest_manager import EventIngestManager, IngestionMetrics


class TestIngestionMetrics:
    """Test metrics tracking."""

    def test_metrics_initialization(self) -> None:
        """Test metrics object initialization."""
        metrics = IngestionMetrics()
        stats = metrics.get_stats()

        assert stats["events_processed"] == 0
        assert stats["events_by_source"] == {}
        assert stats["events_by_parser"] == {}
        assert stats["errors"] == 0

    def test_record_event(self) -> None:
        """Test recording event metrics."""
        metrics = IngestionMetrics()

        metrics.record_event("kafka", "parser1")
        metrics.record_event("kafka", "parser1")
        metrics.record_event("s3", "parser2")

        stats = metrics.get_stats()
        assert stats["events_processed"] == 3
        assert stats["events_by_source"]["kafka"] == 2
        assert stats["events_by_source"]["s3"] == 1
        assert stats["events_by_parser"]["parser1"] == 2
        assert stats["events_by_parser"]["parser2"] == 1

    def test_record_error(self) -> None:
        """Test recording errors."""
        metrics = IngestionMetrics()

        metrics.record_error()
        metrics.record_error()

        stats = metrics.get_stats()
        assert stats["errors"] == 2


class TestEventIngestManager:
    """Test event ingest manager."""

    def test_manager_initialization(self) -> None:
        """Test manager initialization."""
        config: Dict[str, Any] = {
            "message_bus": {
                "type": "memory",
                "output_topic": "raw-events",
            }
        }
        manager = EventIngestManager(config)

        assert manager.config == config
        assert len(manager.sources) == 0
        assert manager.message_bus is None

    @pytest.mark.asyncio
    async def test_manager_initialize_with_no_sources(self) -> None:
        """Test manager initialization with no enabled sources."""
        config: Dict[str, Any] = {
            "message_bus": {
                "type": "memory",
                "output_topic": "raw-events",
            },
            "kafka": {"enabled": False},
            "scol_api": {"enabled": False},
        }
        manager = EventIngestManager(config)
        await manager.initialize()

        assert manager.message_bus is not None
        assert len(manager.sources) == 0

    @pytest.mark.asyncio
    async def test_manager_process_event(self) -> None:
        """Test event processing and publishing."""
        config: Dict[str, Any] = {
            "message_bus": {
                "type": "memory",
                "output_topic": "raw-events",
            }
        }
        manager = EventIngestManager(config)
        await manager.initialize()

        event = {"alert_type": "DLP", "user": "test@example.com"}
        await manager.process_event(event, "netskope_dlp")

        stats = manager.get_metrics()
        assert stats["events_processed"] == 1

    @pytest.mark.asyncio
    async def test_manager_get_metrics(self) -> None:
        """Test getting manager metrics."""
        config: Dict[str, Any] = {
            "message_bus": {
                "type": "memory",
                "output_topic": "raw-events",
            }
        }
        manager = EventIngestManager(config)

        # Process some events
        await manager.initialize()
        await manager.process_event({"data": "1"}, "parser1")
        await manager.process_event({"data": "2"}, "parser1")
        await manager.process_event({"data": "3"}, "parser2")

        stats = manager.get_metrics()
        assert stats["events_processed"] == 3
        assert stats["events_by_parser"]["parser1"] == 2
        assert stats["events_by_parser"]["parser2"] == 1


class TestEventIngestFlow:
    """Test complete event ingestion flow."""

    @pytest.mark.asyncio
    async def test_memory_bus_event_flow(self) -> None:
        """Test event flow through memory message bus."""
        config: Dict[str, Any] = {
            "message_bus": {
                "type": "memory",
                "output_topic": "test-events",
            }
        }
        manager = EventIngestManager(config)
        await manager.initialize()

        # Process an event
        event = {"test": "data"}
        await manager.process_event(event, "test-parser")

        # Verify metrics
        stats = manager.get_metrics()
        assert stats["events_processed"] == 1

        # Cleanup
        await manager.stop()

    @pytest.mark.asyncio
    async def test_manager_stop_graceful(self) -> None:
        """Test graceful shutdown."""
        config: Dict[str, Any] = {
            "message_bus": {
                "type": "memory",
                "output_topic": "test-events",
            }
        }
        manager = EventIngestManager(config)
        await manager.initialize()

        # Should not raise an exception
        await manager.stop()


class TestConfigValidation:
    """Test configuration validation."""

    def test_manager_with_kafka_config(self) -> None:
        """Test manager accepts Kafka config."""
        config: Dict[str, Any] = {
            "message_bus": {"type": "memory"},
            "kafka": {
                "enabled": True,
                "bootstrap_servers": "localhost:9092",
                "topics": ["test"],
                "parser_id": "test-parser",
            },
        }
        manager = EventIngestManager(config)
        assert manager.config["kafka"]["enabled"] is True

    def test_manager_with_scol_config(self) -> None:
        """Test manager accepts SCOL API config."""
        config: Dict[str, Any] = {
            "message_bus": {"type": "memory"},
            "scol_api": {
                "enabled": True,
                "sources": [
                    {
                        "api_url": "https://api.example.com",
                        "auth_token": "token",
                        "checkpoint_key": "key",
                        "parser_id": "parser",
                    }
                ],
            },
        }
        manager = EventIngestManager(config)
        assert manager.config["scol_api"]["enabled"] is True
