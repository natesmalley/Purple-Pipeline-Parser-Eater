"""Unit tests for OutputService."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.output_service import OutputService


@pytest.fixture
def output_config():
    """Create output service configuration."""
    return {
        "message_bus": {
            "type": "memory",
            "input_topic": "ocsf-events",
        },
        "validator": {
            "strict_mode": False,
        },
        "sinks": {
            "observo": {
                "enabled": False,
            },
            "s3_archive": {
                "enabled": False,
            },
        },
        "retry": {
            "max_attempts": 3,
            "base_backoff_seconds": 1,
            "max_backoff_seconds": 5,
        },
    }


@pytest.fixture
def service(output_config):
    """Create OutputService instance."""
    return OutputService(output_config)


@pytest.fixture
def valid_event():
    """Create a valid OCSF event."""
    return {
        "_metadata": {
            "parser_id": "netskope_dlp",
            "parser_version": "1.0.0",
        },
        "log": {
            "class_uid": 2004,
            "category_uid": 2,
            "severity_id": 4,
            "time": 1699363200000,
            "metadata": {
                "version": "1.5.0",
                "product": {
                    "name": "Netskope",
                    "vendor_name": "Netskope"
                }
            }
        }
    }


class TestOutputService:
    """Test OutputService class."""

    def test_initialization(self, service):
        """Test service initializes correctly."""
        assert service.config is not None
        assert service.running is False
        assert service.validator is not None
        assert service.stats["total_received"] == 0

    def test_initialization_with_observo_sink(self, output_config):
        """Test initialization with Observo sink enabled."""
        output_config["sinks"]["observo"]["enabled"] = True
        output_config["sinks"]["observo"]["base_url"] = "https://api.observo.ai"
        output_config["sinks"]["observo"]["api_token"] = "test-token"

        with patch("services.output_service.ObservoIngestClient"):
            service = OutputService(output_config)

            assert "observo" in service.sinks

    def test_initialization_with_s3_sink(self, output_config):
        """Test initialization with S3 sink enabled."""
        output_config["sinks"]["s3_archive"]["enabled"] = True
        output_config["sinks"]["s3_archive"]["bucket"] = "test-bucket"

        with patch("services.output_service.S3ArchiveSink"):
            service = OutputService(output_config)

            assert "s3_archive" in service.sinks

    @pytest.mark.asyncio
    async def test_process_event_valid(self, service, valid_event):
        """Test processing a valid event."""
        await service._process_event(valid_event)

        assert service.stats["total_received"] == 1
        assert service.stats["validation_passed"] == 1
        assert service.stats["validation_failed"] == 0

    @pytest.mark.asyncio
    async def test_process_event_validation_failure(self, service):
        """Test processing event that fails validation."""
        invalid_event = {
            "_metadata": {"parser_id": "test"},
            "log": {
                "class_uid": 2004,
                # Missing required fields
            }
        }

        await service._process_event(invalid_event)

        assert service.stats["total_received"] == 1
        assert service.stats["validation_failed"] == 1

    @pytest.mark.asyncio
    async def test_process_event_missing_log(self, service):
        """Test processing event without log field."""
        event = {
            "_metadata": {"parser_id": "test"},
        }

        await service._process_event(event)

        assert service.stats["total_received"] == 1
        assert service.stats["delivery_failed"] == 1

    @pytest.mark.asyncio
    async def test_process_event_with_sink(self, output_config, valid_event):
        """Test processing event with sink delivery."""
        output_config["sinks"]["observo"]["enabled"] = True
        output_config["sinks"]["observo"]["base_url"] = "https://api.observo.ai"
        output_config["sinks"]["observo"]["api_token"] = "test-token"

        with patch("services.output_service.ObservoIngestClient") as mock_observo:
            mock_client = AsyncMock()
            mock_client.ingest_events.return_value = {
                "accepted": 1,
                "rejected": 0
            }
            mock_observo.return_value = mock_client

            service = OutputService(output_config)
            service.sinks["observo"] = mock_client

            await service._process_event(valid_event)

            assert service.stats["delivery_success"] == 1

    @pytest.mark.asyncio
    async def test_deliver_to_observo_sink_success(self, service, valid_event):
        """Test successful delivery to Observo sink."""
        mock_observo = AsyncMock()
        mock_observo.ingest_events.return_value = {
            "accepted": 1,
            "rejected": 0
        }

        service.sinks["observo"] = mock_observo

        result = await service._deliver_to_sink("observo", mock_observo, valid_event)

        assert result is True
        assert service.stats["by_sink"]["observo"]["success"] == 1

    @pytest.mark.asyncio
    async def test_deliver_to_observo_sink_failure(self, service, valid_event):
        """Test failed delivery to Observo sink."""
        mock_observo = AsyncMock()
        mock_observo.ingest_events.return_value = {
            "accepted": 0,
            "rejected": 1
        }

        service.sinks["observo"] = mock_observo

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await service._deliver_to_sink("observo", mock_observo, valid_event)

            assert result is False
            assert service.stats["by_sink"]["observo"]["failed"] == 1

    @pytest.mark.asyncio
    async def test_deliver_with_retry(self, service, valid_event):
        """Test delivery with retries."""
        mock_sink = AsyncMock()

        call_count = 0

        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return True

        mock_sink.write_event = side_effect

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await service._deliver_to_sink("test_sink", mock_sink, valid_event)

            assert result is True
            assert call_count == 3

    @pytest.mark.asyncio
    async def test_deliver_max_retries_exceeded(self, output_config, valid_event):
        """Test delivery fails after max retries."""
        output_config["retry"]["max_attempts"] = 2

        service = OutputService(output_config)

        mock_sink = AsyncMock()
        mock_sink.write_event.side_effect = Exception("Persistent failure")

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await service._deliver_to_sink("test_sink", mock_sink, valid_event)

            assert result is False
            assert service.stats["by_sink"]["test_sink"]["failed"] == 1

    @pytest.mark.asyncio
    async def test_deliver_exponential_backoff(self, service, valid_event):
        """Test exponential backoff calculation."""
        mock_sink = AsyncMock()
        mock_sink.write_event.side_effect = Exception("Failure")

        sleep_times = []

        async def mock_sleep(duration):
            sleep_times.append(duration)

        with patch("asyncio.sleep", side_effect=mock_sleep):
            await service._deliver_to_sink("test_sink", mock_sink, valid_event)

        assert len(sleep_times) >= 2
        assert sleep_times[0] == 2  # base_backoff
        assert sleep_times[1] == 4  # base_backoff * 2^1

    @pytest.mark.asyncio
    async def test_deliver_max_backoff_capped(self, output_config, valid_event):
        """Test backoff is capped at max_backoff."""
        output_config["retry"]["base_backoff_seconds"] = 10
        output_config["retry"]["max_backoff_seconds"] = 20
        output_config["retry"]["max_attempts"] = 5

        service = OutputService(output_config)

        mock_sink = AsyncMock()
        mock_sink.write_event.side_effect = Exception("Failure")

        sleep_times = []

        async def mock_sleep(duration):
            sleep_times.append(duration)

        with patch("asyncio.sleep", side_effect=mock_sleep):
            await service._deliver_to_sink("test_sink", mock_sink, valid_event)

        for sleep_time in sleep_times:
            assert sleep_time <= 20

    @pytest.mark.asyncio
    async def test_stop(self, service):
        """Test service shutdown."""
        service.running = True
        service.message_bus = AsyncMock()

        await service.stop()

        assert service.running is False
        service.message_bus.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_flushes_s3_sink(self, output_config):
        """Test stop flushes S3 sink."""
        output_config["sinks"]["s3_archive"]["enabled"] = True
        output_config["sinks"]["s3_archive"]["bucket"] = "test-bucket"

        with patch("services.output_service.S3ArchiveSink") as mock_s3:
            mock_client = AsyncMock()
            mock_s3.return_value = mock_client

            service = OutputService(output_config)
            service.message_bus = AsyncMock()

            await service.stop()

            mock_client.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_closes_observo_sink(self, output_config):
        """Test stop closes Observo sink."""
        output_config["sinks"]["observo"]["enabled"] = True
        output_config["sinks"]["observo"]["base_url"] = "https://api.observo.ai"
        output_config["sinks"]["observo"]["api_token"] = "test-token"

        with patch("services.output_service.ObservoIngestClient") as mock_observo:
            mock_client = AsyncMock()
            mock_observo.return_value = mock_client

            service = OutputService(output_config)
            service.message_bus = AsyncMock()

            await service.stop()

            mock_client.close.assert_called_once()

    def test_get_statistics(self, service):
        """Test get_statistics returns correct format."""
        service.stats["total_received"] = 100
        service.stats["validation_passed"] = 95
        service.stats["validation_failed"] = 5
        service.stats["delivery_success"] = 90
        service.stats["delivery_failed"] = 5

        stats = service.get_statistics()

        assert stats["total_received"] == 100
        assert stats["validation_passed"] == 95

    def test_get_statistics_with_sink_metrics(self, service):
        """Test statistics include per-sink metrics."""
        service.stats["by_sink"]["observo"]["success"] = 50
        service.stats["by_sink"]["observo"]["latency_ms"] = [10.0, 20.0, 30.0]

        stats = service.get_statistics()

        assert "observo" in stats["by_sink"]
        assert stats["by_sink"]["observo"]["success"] == 50
        assert stats["by_sink"]["observo"]["avg_latency_ms"] == 20.0
        assert stats["by_sink"]["observo"]["max_latency_ms"] == 30.0

    @pytest.mark.asyncio
    async def test_multiple_events_processing(self, service, valid_event):
        """Test processing multiple events."""
        for _ in range(5):
            await service._process_event(valid_event)

        assert service.stats["total_received"] == 5
        assert service.stats["validation_passed"] == 5

    @pytest.mark.asyncio
    async def test_error_handling_during_processing(self, service):
        """Test service handles errors during event processing."""
        event = {
            "_metadata": {},
            "log": {},
        }

        await service._process_event(event)

        assert service.stats["total_received"] == 1
