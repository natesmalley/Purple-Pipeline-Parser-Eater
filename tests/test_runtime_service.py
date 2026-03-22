"""Unit tests for RuntimeService."""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from services.runtime_service import RuntimeService
from components.message_bus_adapter import Message


@pytest.fixture
def runtime_config():
    """Provide test configuration."""
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
        "manifest_directory": "output",
        "lua_cache_size": 10,
        "canary": {
            "promotion_threshold": 100,
            "error_tolerance": 0.05
        },
        "error_handling": {
            "dlq_enabled": True,
            "dlq_topic": "transform-errors"
        }
    }


@pytest.fixture
def sample_message():
    """Provide a sample message."""
    return Message(
        value={
            "id": "event-123",
            "alert_type": "DLP",
            "user": "john@example.com",
            "file": "sensitive.xlsx"
        },
        headers={"parser_id": "netskope_dlp"}
    )


@pytest.fixture
def sample_manifest():
    """Mock manifest data."""
    manifest = Mock()
    manifest.version.semantic = "1.0.0"
    manifest.lua_metadata = Mock()
    manifest.lua_metadata.file = "transform.lua"
    manifest.deployment = Mock()
    manifest.deployment.canary_percentage = 10
    return manifest


class TestRuntimeServiceInitialization:
    """Tests for RuntimeService initialization."""

    def test_init_with_default_config(self, runtime_config):
        """Test initialization with provided config."""
        service = RuntimeService(runtime_config)

        assert service.config == runtime_config
        assert service.running is False
        assert service.input_topic == "raw-security-events"
        assert service.output_topic == "ocsf-events"
        assert service.manifest_store is not None
        assert service.executor is not None
        assert service.canary_router is not None
        assert service.runtime_metrics is not None

    def test_init_statistics(self, runtime_config):
        """Test initial statistics."""
        service = RuntimeService(runtime_config)

        assert service.stats["total_events"] == 0
        assert service.stats["successful_transforms"] == 0
        assert service.stats["failed_transforms"] == 0
        assert len(service.stats["parsers_active"]) == 0

    def test_init_web_ui_state(self, runtime_config):
        """Test web UI integration state."""
        service = RuntimeService(runtime_config)

        assert service.metrics == {}
        assert service.reload_requests == {}
        assert service.pending_promotions == {}


class TestRuntimeServiceMessaging:
    """Tests for message handling."""

    @pytest.mark.asyncio
    async def test_message_receives_updates_stats(self, runtime_config, sample_message, sample_manifest):
        """Test that message processing updates statistics."""
        service = RuntimeService(runtime_config)

        # Mock manifest store
        service.manifest_store = Mock()
        service.manifest_store.load_manifest = Mock(return_value=sample_manifest)
        service.manifest_store.load_lua = Mock(return_value="function processEvent(e) return {} end")

        # Mock executor
        service.executor = AsyncMock()
        service.executor.execute = AsyncMock(return_value=(False, {"error": "test"}))

        await service._handle_message(sample_message)

        assert service.stats["total_events"] == 1
        assert "netskope_dlp" in service.stats["parsers_active"]

    @pytest.mark.asyncio
    async def test_successful_transform(self, runtime_config, sample_message, sample_manifest):
        """Test successful event transformation."""
        service = RuntimeService(runtime_config)
        service.bus = AsyncMock()

        # Mock components
        service.manifest_store = Mock()
        service.manifest_store.load_manifest = Mock(return_value=sample_manifest)
        service.manifest_store.load_lua = Mock(return_value="function processEvent(e) return {class_uid=1} end")

        service.executor = AsyncMock()
        service.executor.execute = AsyncMock(return_value=(True, {"class_uid": 1}))

        await service._handle_message(sample_message)

        assert service.stats["successful_transforms"] == 1
        assert service.stats["failed_transforms"] == 0
        assert service.bus.publish.called

    @pytest.mark.asyncio
    async def test_failed_transform_sends_to_dlq(self, runtime_config, sample_message, sample_manifest):
        """Test that failed transforms are sent to DLQ."""
        service = RuntimeService(runtime_config)
        service.bus = AsyncMock()

        # Mock components
        service.manifest_store = Mock()
        service.manifest_store.load_manifest = Mock(return_value=sample_manifest)
        service.manifest_store.load_lua = Mock(return_value="invalid lua")

        service.executor = AsyncMock()
        service.executor.execute = AsyncMock(return_value=(False, {"error": "Execution failed"}))

        await service._handle_message(sample_message)

        assert service.stats["failed_transforms"] == 1

        # Check DLQ publish was called
        calls = service.bus.publish.call_args_list
        dlq_call = next((c for c in calls if "transform-errors" in str(c)), None)
        assert dlq_call is not None

    @pytest.mark.asyncio
    async def test_missing_manifest(self, runtime_config, sample_message):
        """Test handling of missing manifest."""
        service = RuntimeService(runtime_config)
        service.bus = AsyncMock()

        service.manifest_store = Mock()
        service.manifest_store.load_manifest = Mock(return_value=None)
        service.canary_router.versions = {}

        await service._handle_message(sample_message)

        assert service.stats["failed_transforms"] == 1


class TestRuntimeServiceMetrics:
    """Tests for metrics collection."""

    def test_update_metrics(self, runtime_config):
        """Test updating metrics."""
        service = RuntimeService(runtime_config)

        metrics = {"parser1": {"total": 100, "success": 95}}

        service.update_metrics(metrics)

        assert service.metrics["parser1"]["total"] == 100

    def test_get_runtime_status(self, runtime_config):
        """Test getting runtime status."""
        service = RuntimeService(runtime_config)
        service.stats["total_events"] = 50
        service.stats["successful_transforms"] = 48
        service.stats["failed_transforms"] = 2

        status = service.get_runtime_status()

        assert status["running"] is False
        assert status["stats"]["total_events"] == 50
        assert status["stats"]["successful"] == 48
        assert status["stats"]["failed"] == 2
        assert abs(status["stats"]["success_rate"] - 0.96) < 0.01

    def test_get_statistics(self, runtime_config):
        """Test getting statistics."""
        service = RuntimeService(runtime_config)
        service.stats["total_events"] = 10
        service.stats["successful_transforms"] = 9

        stats = service.get_statistics()

        assert stats["stats"]["total_events"] == 10


class TestRuntimeServiceWebUIIntegration:
    """Tests for web UI integration."""

    def test_request_runtime_reload(self, runtime_config):
        """Test requesting runtime reload."""
        service = RuntimeService(runtime_config)

        result = service.request_runtime_reload("test_parser")

        assert result is True
        assert service.reload_requests["test_parser"] == "pending"

    def test_pop_reload_request(self, runtime_config):
        """Test popping reload request."""
        service = RuntimeService(runtime_config)
        service.reload_requests["test_parser"] = "pending"

        result = service.pop_reload_request("test_parser")

        assert result == "pending"
        assert "test_parser" not in service.reload_requests

    def test_request_canary_promotion(self, runtime_config):
        """Test requesting canary promotion."""
        service = RuntimeService(runtime_config)

        result = service.request_canary_promotion("test_parser")

        assert result is True
        assert service.pending_promotions["test_parser"] == "pending"

    def test_pop_canary_promotion(self, runtime_config):
        """Test popping canary promotion."""
        service = RuntimeService(runtime_config)
        service.pending_promotions["test_parser"] = "pending"

        result = service.pop_canary_promotion("test_parser")

        assert result == "pending"
        assert "test_parser" not in service.pending_promotions


class TestRuntimeServiceErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_handle_transform_error_with_dlq(self, runtime_config):
        """Test error handling with DLQ."""
        service = RuntimeService(runtime_config)
        service.bus = AsyncMock()

        event = {"data": "test"}
        parser_id = "test_parser"
        error = "Processing failed"

        await service._handle_transform_error(event, parser_id, error)

        assert service.bus.publish.called
        call_args = service.bus.publish.call_args

        # Verify DLQ topic and error structure
        assert "transform-errors" in call_args[0]

    @pytest.mark.asyncio
    async def test_handle_transform_error_disabled_dlq(self, runtime_config):
        """Test error handling with DLQ disabled."""
        config = runtime_config.copy()
        config["error_handling"]["dlq_enabled"] = False

        service = RuntimeService(config)
        service.bus = AsyncMock()

        await service._handle_transform_error({}, "parser", "error")

        # DLQ should not be called
        assert not service.bus.publish.called


class TestRuntimeServiceCanaryPromotion:
    """Tests for canary promotion logic."""

    @pytest.mark.asyncio
    async def test_canary_promotion_detection(self, runtime_config, sample_message, sample_manifest):
        """Test detection of canary promotion readiness."""
        service = RuntimeService(runtime_config)
        service.bus = AsyncMock()
        service.pending_promotions["netskope_dlp"] = "pending"

        # Mock components
        service.manifest_store = Mock()
        service.manifest_store.load_manifest = Mock(return_value=sample_manifest)
        service.manifest_store.load_lua = Mock(return_value="function processEvent(e) return {} end")

        service.executor = AsyncMock()
        service.executor.execute = AsyncMock(return_value=(True, {}))

        # Mock canary router to return promotion ready
        service.canary_router.should_promote_canary = Mock(return_value=True)

        await service._handle_message(sample_message)

        # Check promotion status
        assert service.pending_promotions.get("netskope_dlp") == "ready"


class TestRuntimeServiceShutdown:
    """Tests for shutdown procedure."""

    @pytest.mark.asyncio
    async def test_stop_closes_resources(self, runtime_config):
        """Test that stop() properly closes resources."""
        service = RuntimeService(runtime_config)

        # Mock resources
        service.executor = AsyncMock()
        service.bus = AsyncMock()

        await service.stop()

        assert service.running is False
        assert service.executor.close.called
        assert service.bus.close.called

    @pytest.mark.asyncio
    async def test_stop_logs_statistics(self, runtime_config):
        """Test that stop() logs final statistics."""
        service = RuntimeService(runtime_config)
        service.stats["total_events"] = 100
        service.stats["successful_transforms"] = 99

        service.executor = AsyncMock()
        service.bus = AsyncMock()

        with patch("services.runtime_service.logger") as mock_logger:
            await service.stop()

            # Verify logging occurred
            assert mock_logger.info.called
