"""End-to-end integration tests for output pipeline."""

from unittest.mock import AsyncMock, patch

import pytest

from components.message_bus_adapter import MemoryAdapter, Message
from components.observo_ingest_client import ObservoIngestClient
from components.output_validator import OutputValidator
from components.sinks.s3_archive_sink import S3ArchiveSink
from services.output_service import OutputService


@pytest.fixture
def memory_bus():
    """Create in-memory message bus."""
    return MemoryAdapter()


@pytest.fixture
def valid_event():
    """Create a valid OCSF event."""
    return {
        "_metadata": {
            "source_type": "kafka",
            "parser_id": "netskope_dlp",
            "parser_version": "1.0.0",
            "transform_time": "2025-11-07T12:00:01Z",
            "execution_time_ms": 12.5,
        },
        "log": {
            "class_uid": 2004,
            "class_name": "Detection Finding",
            "category_uid": 2,
            "severity_id": 4,
            "time": 1699363200000,
            "user": {
                "name": "john@example.com",
                "email_addr": "john@example.com"
            },
            "metadata": {
                "version": "1.5.0",
                "product": {
                    "name": "Netskope",
                    "vendor_name": "Netskope"
                }
            }
        }
    }


class TestEndToEndPipeline:
    """End-to-end integration tests."""

    @pytest.mark.asyncio
    async def test_event_ingestion_and_validation(self, memory_bus, valid_event):
        """Test event ingestion and validation through message bus."""
        message = Message(value=valid_event, headers={})
        await memory_bus.publish("ocsf-events", message)

        received_message = None
        async for msg in memory_bus.subscribe("ocsf-events"):
            received_message = msg
            break

        assert received_message is not None
        assert received_message.value == valid_event

        validator = OutputValidator()
        is_valid = validator.validate_ocsf(valid_event["log"])
        assert is_valid is True

    @pytest.mark.asyncio
    async def test_validator_catches_invalid_events(self, memory_bus):
        """Test validator catches invalid events."""
        invalid_event = {
            "_metadata": {"parser_id": "test"},
            "log": {
                "class_uid": "invalid",  # Should be integer
                "category_uid": 2,
                "severity_id": 4,
                "time": 1699363200000,
                "metadata": {
                    "version": "1.5.0",
                    "product": {"name": "Test"}
                }
            }
        }

        validator = OutputValidator()
        is_valid = validator.validate_ocsf(invalid_event["log"])
        assert is_valid is False

    @pytest.mark.asyncio
    async def test_full_pipeline_with_memory_sink(self):
        """Test full pipeline with memory sink."""
        config = {
            "message_bus": {
                "type": "memory",
                "input_topic": "ocsf-events",
            },
            "validator": {
                "strict_mode": False,
            },
            "sinks": {
                "observo": {"enabled": False},
                "s3_archive": {"enabled": False},
            },
            "retry": {
                "max_attempts": 3,
                "base_backoff_seconds": 1,
                "max_backoff_seconds": 5,
            },
        }

        service = OutputService(config)

        valid_event = {
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

        await service._process_event(valid_event)

        assert service.stats["total_received"] == 1
        assert service.stats["validation_passed"] == 1
        assert service.stats["validation_failed"] == 0

    @pytest.mark.asyncio
    async def test_pipeline_with_observo_sink(self):
        """Test pipeline with Observo sink."""
        config = {
            "message_bus": {
                "type": "memory",
                "input_topic": "ocsf-events",
            },
            "validator": {
                "strict_mode": False,
            },
            "sinks": {
                "observo": {
                    "enabled": True,
                    "base_url": "https://api.observo.ai",
                    "api_token": "test-token",
                    "batch_size": 100,
                },
                "s3_archive": {"enabled": False},
            },
            "retry": {
                "max_attempts": 2,
                "base_backoff_seconds": 1,
                "max_backoff_seconds": 5,
            },
        }

        with patch("services.output_service.ObservoIngestClient") as mock_observo:
            mock_client = AsyncMock()
            mock_client.ingest_events.return_value = {
                "accepted": 1,
                "rejected": 0
            }
            mock_observo.return_value = mock_client

            service = OutputService(config)

            valid_event = {
                "_metadata": {
                    "parser_id": "netskope_dlp",
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

            await service._process_event(valid_event)

            assert service.stats["delivery_success"] == 1
            mock_client.ingest_events.assert_called_once()

    @pytest.mark.asyncio
    async def test_pipeline_with_s3_sink(self):
        """Test pipeline with S3 sink."""
        config = {
            "message_bus": {
                "type": "memory",
                "input_topic": "ocsf-events",
            },
            "validator": {
                "strict_mode": False,
            },
            "sinks": {
                "observo": {"enabled": False},
                "s3_archive": {
                    "enabled": True,
                    "bucket": "test-bucket",
                    "prefix": "test-prefix",
                    "batch_size": 1000,
                },
            },
            "retry": {
                "max_attempts": 2,
                "base_backoff_seconds": 1,
                "max_backoff_seconds": 5,
            },
        }

        with patch("services.output_service.S3ArchiveSink") as mock_s3:
            mock_client = AsyncMock()
            mock_client.write_event.return_value = True
            mock_s3.return_value = mock_client

            service = OutputService(config)

            valid_event = {
                "_metadata": {
                    "parser_id": "netskope_dlp",
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

            await service._process_event(valid_event)

            assert service.stats["delivery_success"] == 1
            mock_client.write_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_pipeline_with_multiple_sinks(self):
        """Test pipeline with multiple sinks enabled."""
        config = {
            "message_bus": {
                "type": "memory",
                "input_topic": "ocsf-events",
            },
            "validator": {
                "strict_mode": False,
            },
            "sinks": {
                "observo": {
                    "enabled": True,
                    "base_url": "https://api.observo.ai",
                    "api_token": "test-token",
                },
                "s3_archive": {
                    "enabled": True,
                    "bucket": "test-bucket",
                },
            },
            "retry": {
                "max_attempts": 2,
                "base_backoff_seconds": 1,
                "max_backoff_seconds": 5,
            },
        }

        with patch("services.output_service.ObservoIngestClient") as mock_observo, \
             patch("services.output_service.S3ArchiveSink") as mock_s3:

            mock_observo_client = AsyncMock()
            mock_observo_client.ingest_events.return_value = {
                "accepted": 1,
                "rejected": 0
            }
            mock_observo.return_value = mock_observo_client

            mock_s3_client = AsyncMock()
            mock_s3_client.write_event.return_value = True
            mock_s3.return_value = mock_s3_client

            service = OutputService(config)

            valid_event = {
                "_metadata": {
                    "parser_id": "netskope_dlp",
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

            await service._process_event(valid_event)

            assert service.stats["delivery_success"] == 1
            mock_observo_client.ingest_events.assert_called_once()
            mock_s3_client.write_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_pipeline_batch_events(self):
        """Test pipeline handling batch events."""
        config = {
            "message_bus": {
                "type": "memory",
                "input_topic": "ocsf-events",
            },
            "validator": {
                "strict_mode": False,
            },
            "sinks": {
                "observo": {"enabled": False},
                "s3_archive": {"enabled": False},
            },
            "retry": {
                "max_attempts": 2,
                "base_backoff_seconds": 1,
                "max_backoff_seconds": 5,
            },
        }

        service = OutputService(config)

        valid_event = {
            "_metadata": {
                "parser_id": "netskope_dlp",
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

        for _ in range(10):
            await service._process_event(valid_event)

        assert service.stats["total_received"] == 10
        assert service.stats["validation_passed"] == 10

    @pytest.mark.asyncio
    async def test_pipeline_mixed_valid_invalid_events(self):
        """Test pipeline with mix of valid and invalid events."""
        config = {
            "message_bus": {
                "type": "memory",
                "input_topic": "ocsf-events",
            },
            "validator": {
                "strict_mode": False,
            },
            "sinks": {
                "observo": {"enabled": False},
                "s3_archive": {"enabled": False},
            },
            "retry": {
                "max_attempts": 2,
                "base_backoff_seconds": 1,
                "max_backoff_seconds": 5,
            },
        }

        service = OutputService(config)

        valid_event = {
            "_metadata": {"parser_id": "netskope_dlp"},
            "log": {
                "class_uid": 2004,
                "category_uid": 2,
                "severity_id": 4,
                "time": 1699363200000,
                "metadata": {
                    "version": "1.5.0",
                    "product": {"name": "Netskope", "vendor_name": "Netskope"}
                }
            }
        }

        invalid_event = {
            "_metadata": {"parser_id": "test"},
            "log": {
                "class_uid": 2004,
            }
        }

        await service._process_event(valid_event)
        await service._process_event(invalid_event)
        await service._process_event(valid_event)

        assert service.stats["total_received"] == 3
        assert service.stats["validation_passed"] == 2
        assert service.stats["validation_failed"] == 1

    @pytest.mark.asyncio
    async def test_statistics_accuracy(self):
        """Test statistics are accurate for complete pipeline."""
        config = {
            "message_bus": {
                "type": "memory",
                "input_topic": "ocsf-events",
            },
            "validator": {
                "strict_mode": False,
            },
            "sinks": {
                "observo": {"enabled": False},
                "s3_archive": {"enabled": False},
            },
            "retry": {
                "max_attempts": 2,
                "base_backoff_seconds": 1,
                "max_backoff_seconds": 5,
            },
        }

        service = OutputService(config)

        valid_event = {
            "_metadata": {"parser_id": "netskope_dlp"},
            "log": {
                "class_uid": 2004,
                "category_uid": 2,
                "severity_id": 4,
                "time": 1699363200000,
                "metadata": {
                    "version": "1.5.0",
                    "product": {"name": "Netskope", "vendor_name": "Netskope"}
                }
            }
        }

        for _ in range(5):
            await service._process_event(valid_event)

        stats = service.get_statistics()

        assert stats["total_received"] == 5
        assert stats["validation_passed"] == 5
        assert stats["validation_failed"] == 0
