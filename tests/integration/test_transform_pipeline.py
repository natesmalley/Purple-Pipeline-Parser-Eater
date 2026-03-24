"""Integration tests for the transform pipeline."""

import pytest
import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from services.runtime_service import RuntimeService
from services.transform_worker import TransformWorker
from components.message_bus_adapter import Message, create_bus_adapter


@pytest.fixture
def temp_manifest_and_lua():
    """Create temporary manifest and Lua files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create parser directory
        parser_dir = tmpdir_path / "test_parser"
        parser_dir.mkdir()

        # Create manifest
        manifest = {
            "parser_id": "test_parser",
            "version": {
                "semantic": "1.0.0"
            },
            "lua_metadata": {
                "file": "transform.lua"
            },
            "deployment": {
                "canary_percentage": 0  # No canary for tests
            }
        }
        (parser_dir / "manifest.json").write_text(json.dumps(manifest))

        # Create Lua transformation
        lua_code = """
function processEvent(event)
    local result = {}
    result.class_uid = 2004
    result.category_uid = 2
    result.severity_id = 4
    result.time = 1699363200000
    result.metadata = {
        version = "1.5.0",
        product = {
            name = "Test",
            vendor_name = "Test"
        }
    }
    result.alert_type = event.alert_type
    result.user = event.user
    return result
end
"""
        (parser_dir / "transform.lua").write_text(lua_code)

        yield tmpdir_path


@pytest.fixture
def pipeline_config(temp_manifest_and_lua):
    """Create configuration for pipeline."""
    return {
        "message_bus": {
            "type": "memory",
            "input_topic": "raw-security-events",
            "output_topic": "ocsf-events",
            "consumer_group": "test-workers"
        },
        "executor": {
            "type": "lupa"
        },
        "transform_worker": {
            "input_topic": "raw-security-events",
            "output_topic": "ocsf-events"
        },
        "manifest_directory": str(temp_manifest_and_lua),
        "canary": {
            "promotion_threshold": 1000,
            "error_tolerance": 0.01
        },
        "error_handling": {
            "dlq_enabled": True,
            "dlq_topic": "transform-errors"
        }
    }


class TestTransformPipelineIntegration:
    """Integration tests for the complete transform pipeline."""

    @pytest.mark.asyncio
    async def test_end_to_end_event_transformation(self, pipeline_config):
        """Test complete flow from raw event to OCSF output."""
        service = RuntimeService(pipeline_config)

        # Create test event
        test_event = Message(
            value={
                "id": "test-event-001",
                "alert_type": "DLP",
                "user": "john@example.com",
                "file": "sensitive.xlsx"
            },
            headers={"parser_id": "test_parser"}
        )

        # Capture published events
        published_events = []

        async def capture_publish(topic, message):
            published_events.append((topic, message))

        service.bus.publish = capture_publish

        # Process event
        await service._handle_message(test_event)

        # Verify output
        assert len(published_events) == 1

        output_topic, output_message = published_events[0]
        assert output_topic == "ocsf-events"

        output_event = output_message.value
        assert "_metadata" in output_event
        assert "log" in output_event

        # Verify OCSF compliance
        ocsf_log = output_event["log"]
        assert ocsf_log["class_uid"] == 2004
        assert ocsf_log["category_uid"] == 2
        assert ocsf_log["severity_id"] == 4
        assert ocsf_log["time"] == 1699363200000
        assert "metadata" in ocsf_log

        # Verify metadata preservation
        assert output_event["_metadata"]["parser_id"] == "test_parser"
        assert output_event["_metadata"]["parser_version"] == "1.0.0"
        assert "execution_time_ms" in output_event["_metadata"]

    @pytest.mark.asyncio
    async def test_metrics_collection(self, pipeline_config):
        """Test that metrics are collected correctly."""
        service = RuntimeService(pipeline_config)

        # Mock bus
        service.bus.publish = lambda *args, **kwargs: None

        test_event = Message(
            value={"id": "test-001", "alert_type": "DLP", "user": "test@example.com"},
            headers={"parser_id": "test_parser"}
        )

        await service._handle_message(test_event)

        # Check statistics
        assert service.stats["total_events"] == 1
        assert service.stats["successful_transforms"] == 1
        assert "test_parser" in service.stats["parsers_active"]

        # Check metrics
        assert "test_parser" in service.metrics

    @pytest.mark.asyncio
    async def test_error_event_to_dlq(self, pipeline_config):
        """Test that errors are sent to DLQ."""
        service = RuntimeService(pipeline_config)

        # Create a parser that doesn't exist
        test_event = Message(
            value={"id": "test-001", "alert_type": "DLP"},
            headers={"parser_id": "nonexistent_parser"}
        )

        # Capture DLQ events
        dlq_events = []

        async def capture_publish(topic, message):
            if "transform-errors" in topic:
                dlq_events.append((topic, message))

        service.bus.publish = capture_publish

        await service._handle_message(test_event)

        # Verify error was sent to DLQ
        assert len(dlq_events) == 1
        assert service.stats["failed_transforms"] == 1

    @pytest.mark.asyncio
    async def test_manifest_caching(self, pipeline_config):
        """Test that manifests are cached across events."""
        service = RuntimeService(pipeline_config)

        service.bus.publish = lambda *args, **kwargs: None

        # Process multiple events
        for i in range(3):
            test_event = Message(
                value={"id": f"test-{i:03d}", "alert_type": "DLP", "user": "test@example.com"},
                headers={"parser_id": "test_parser"}
            )
            await service._handle_message(test_event)

        # Verify all events were processed
        assert service.stats["total_events"] == 3
        assert service.stats["successful_transforms"] == 3

    @pytest.mark.asyncio
    async def test_lua_cache_effectiveness(self, pipeline_config):
        """Test that Lua code caching improves performance."""
        service = RuntimeService(pipeline_config)

        service.bus.publish = lambda *args, **kwargs: None

        # Load Lua code first time
        cache_stats_before = service.lua_cache.get_stats()

        # Process events
        for i in range(5):
            test_event = Message(
                value={"id": f"test-{i:03d}", "alert_type": "DLP", "user": "test@example.com"},
                headers={"parser_id": "test_parser"}
            )
            await service._handle_message(test_event)

        cache_stats_after = service.lua_cache.get_stats()

        # Verify cache is being used
        assert cache_stats_after["hits"] > 0
        assert cache_stats_after["hit_rate"] > 0

    @pytest.mark.asyncio
    async def test_multiple_parsers_routing(self, temp_manifest_and_lua):
        """Test routing between multiple parsers."""
        # Create second parser
        parser2_dir = temp_manifest_and_lua / "test_parser2"
        parser2_dir.mkdir()

        manifest2 = {
            "parser_id": "test_parser2",
            "version": {"semantic": "1.0.0"},
            "lua_metadata": {"file": "transform.lua"}
        }
        (parser2_dir / "manifest.json").write_text(json.dumps(manifest2))

        lua_code = """
function processEvent(event)
    local result = {}
    result.class_uid = 3001
    result.category_uid = 3
    result.severity_id = 2
    result.time = 1699363200000
    result.metadata = {
        version = "1.5.0",
        product = {name = "Test2", vendor_name = "Test2"}
    }
    return result
end
"""
        (parser2_dir / "transform.lua").write_text(lua_code)

        # Create config
        config = {
            "message_bus": {"type": "memory", "input_topic": "raw-events", "output_topic": "ocsf-events"},
            "executor": {"type": "lupa"},
            "transform_worker": {"input_topic": "raw-events", "output_topic": "ocsf-events"},
            "manifest_directory": str(temp_manifest_and_lua),
            "error_handling": {"dlq_enabled": False}
        }

        service = RuntimeService(config)
        service.bus.publish = lambda *args, **kwargs: None

        # Process events from both parsers
        event1 = Message(
            value={"id": "e1", "alert_type": "DLP", "user": "test@example.com"},
            headers={"parser_id": "test_parser"}
        )

        event2 = Message(
            value={"id": "e2", "alert_type": "ANOMALY", "user": "test@example.com"},
            headers={"parser_id": "test_parser2"}
        )

        await service._handle_message(event1)
        await service._handle_message(event2)

        # Verify both parsers were processed
        assert "test_parser" in service.stats["parsers_active"]
        assert "test_parser2" in service.stats["parsers_active"]
        assert service.stats["successful_transforms"] == 2


class TestTransformWorkerIntegration:
    """Integration tests for TransformWorker."""

    @pytest.mark.asyncio
    async def test_transform_worker_message_handling(self, pipeline_config):
        """Test that TransformWorker handles messages correctly."""
        # Create worker
        worker = TransformWorker(pipeline_config)

        # Create test message
        test_message = Message(
            value={
                "id": "test-001",
                "alert_type": "DLP",
                "user": "john@example.com"
            },
            headers={"parser_id": "test_parser"}
        )

        # Capture output
        output_messages = []

        async def capture_publish(topic, message):
            output_messages.append((topic, message))

        worker.bus.publish = capture_publish

        # Handle message
        await worker._handle_message(test_message)

        # Verify output
        assert len(output_messages) == 1

    @pytest.mark.asyncio
    async def test_transform_worker_canary_routing(self, pipeline_config):
        """Test canary routing in transform worker."""
        worker = TransformWorker(pipeline_config)

        # Process multiple messages to test canary logic
        for i in range(100):
            test_message = Message(
                value={"id": f"event-{i:04d}", "alert_type": "DLP", "user": "test@example.com"},
                headers={"parser_id": "test_parser"}
            )

            # Mock to prevent actual publishing
            worker.bus.publish = lambda *args, **kwargs: None

            await worker._handle_message(test_message)

        # Verify metrics collected
        assert "test_parser" in worker.runtime_metrics.metrics
