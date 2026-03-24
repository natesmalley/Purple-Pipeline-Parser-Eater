"""Unit tests for S3ArchiveSink."""

import gzip
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from components.sinks.s3_archive_sink import S3ArchiveSink


@pytest.fixture
def mock_boto3():
    """Mock boto3."""
    with patch("components.sinks.s3_archive_sink.boto3") as mock:
        mock.client.return_value = MagicMock()
        yield mock


@pytest.fixture
def s3_sink(mock_boto3):
    """Create S3ArchiveSink instance."""
    return S3ArchiveSink(
        bucket_name="test-bucket",
        prefix="test-prefix",
        aws_region="us-east-1",
        batch_size=2,
        compression=True,
    )


@pytest.fixture
def sample_event():
    """Create a sample OCSF event."""
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
        }
    }


class TestS3ArchiveSink:
    """Test S3ArchiveSink class."""

    def test_initialization(self, s3_sink):
        """Test sink initializes correctly."""
        assert s3_sink.bucket_name == "test-bucket"
        assert s3_sink.prefix == "test-prefix"
        assert s3_sink.batch_size == 2
        assert s3_sink.compression is True
        assert len(s3_sink.buffer) == 0

    def test_initialization_requires_boto3(self):
        """Test initialization fails without boto3."""
        with patch("components.sinks.s3_archive_sink.boto3", None):
            with pytest.raises(ImportError):
                S3ArchiveSink(bucket_name="test-bucket")

    @pytest.mark.asyncio
    async def test_write_event(self, s3_sink, sample_event):
        """Test write_event adds event to buffer."""
        result = await s3_sink.write_event(sample_event)

        assert result is True
        assert len(s3_sink.buffer) == 1

    @pytest.mark.asyncio
    async def test_write_event_triggers_flush(self, s3_sink, sample_event):
        """Test write_event triggers flush when buffer full."""
        with patch.object(s3_sink, "flush") as mock_flush:
            mock_flush.return_value = True

            await s3_sink.write_event(sample_event)
            await s3_sink.write_event(sample_event)

            mock_flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_events(self, s3_sink, sample_event):
        """Test write_events adds multiple events."""
        events = [sample_event] * 3
        result = await s3_sink.write_events(events)

        assert result is True
        assert len(s3_sink.buffer) == 1  # One flushed, one remaining

    @pytest.mark.asyncio
    async def test_flush_empty_buffer(self, s3_sink):
        """Test flush with empty buffer."""
        result = await s3_sink.flush()

        assert result is True
        assert len(s3_sink.buffer) == 0

    @pytest.mark.asyncio
    async def test_flush_groups_by_parser_id(self, s3_sink):
        """Test flush groups events by parser_id."""
        event1 = {
            "_metadata": {"parser_id": "parser1"},
            "log": {"class_uid": 2004}
        }
        event2 = {
            "_metadata": {"parser_id": "parser2"},
            "log": {"class_uid": 2004}
        }

        s3_sink.buffer = [event1, event2]

        with patch.object(s3_sink, "_upload_partition") as mock_upload:
            mock_upload.return_value = None

            result = await s3_sink.flush()

            assert result is True
            assert mock_upload.call_count == 2

    @pytest.mark.asyncio
    async def test_flush_clears_buffer(self, s3_sink, sample_event):
        """Test flush clears buffer after successful upload."""
        s3_sink.buffer = [sample_event]

        with patch.object(s3_sink, "_upload_partition") as mock_upload:
            mock_upload.return_value = None

            await s3_sink.flush()

            assert len(s3_sink.buffer) == 0

    @pytest.mark.asyncio
    async def test_flush_error_handling(self, s3_sink, sample_event):
        """Test flush handles errors gracefully."""
        s3_sink.buffer = [sample_event]

        with patch.object(s3_sink, "_upload_partition") as mock_upload:
            mock_upload.side_effect = Exception("Upload failed")

            result = await s3_sink.flush()

            assert result is False
            assert s3_sink.stats["errors"] == 1

    @pytest.mark.asyncio
    async def test_upload_partition_with_compression(self, s3_sink, sample_event):
        """Test _upload_partition with gzip compression."""
        with patch.object(s3_sink, "_upload_partition", wraps=s3_sink._upload_partition) as mock_upload:
            with patch.object(s3_sink.s3_client, "upload_file") as mock_s3_upload:
                await s3_sink._upload_partition("test_parser", [sample_event])

                mock_s3_upload.assert_called_once()
                call_args = mock_s3_upload.call_args
                key = call_args[0][2]
                assert key.endswith(".jsonl.gz")

    @pytest.mark.asyncio
    async def test_upload_partition_without_compression(self, mock_boto3, sample_event):
        """Test _upload_partition without compression."""
        sink = S3ArchiveSink(
            bucket_name="test-bucket",
            compression=False,
        )

        with patch.object(sink.s3_client, "upload_file") as mock_s3_upload:
            await sink._upload_partition("test_parser", [sample_event])

            mock_s3_upload.assert_called_once()
            call_args = mock_s3_upload.call_args
            key = call_args[0][2]
            assert key.endswith(".jsonl")
            assert ".gz" not in key

    @pytest.mark.asyncio
    async def test_upload_partition_partitioning(self, s3_sink, sample_event):
        """Test _upload_partition creates correct S3 key structure."""
        with patch.object(s3_sink.s3_client, "upload_file") as mock_s3_upload:
            await s3_sink._upload_partition("netskope_dlp", [sample_event])

            call_args = mock_s3_upload.call_args
            key = call_args[0][2]

            assert "test-prefix/" in key
            assert "year=" in key
            assert "month=" in key
            assert "day=" in key
            assert "hour=" in key
            assert "parser_id=netskope_dlp" in key

    @pytest.mark.asyncio
    async def test_upload_partition_updates_stats(self, s3_sink, sample_event):
        """Test _upload_partition updates statistics."""
        with patch.object(s3_sink.s3_client, "upload_file") as mock_s3_upload:
            await s3_sink._upload_partition("test_parser", [sample_event])

            assert s3_sink.stats["total_archived"] == 1
            assert s3_sink.stats["total_files"] == 1
            assert s3_sink.stats["total_bytes"] > 0

    def test_get_statistics(self, s3_sink):
        """Test get_statistics returns correct format."""
        s3_sink.stats["total_archived"] = 1000
        s3_sink.stats["total_files"] = 10
        s3_sink.stats["total_bytes"] = 50000
        s3_sink.buffer = [{"test": "event"}]

        stats = s3_sink.get_statistics()

        assert stats["total_archived"] == 1000
        assert stats["total_files"] == 10
        assert stats["buffer_size"] == 1

    @pytest.mark.asyncio
    async def test_close_flushes_buffer(self, s3_sink, sample_event):
        """Test close flushes buffered events."""
        s3_sink.buffer = [sample_event]

        with patch.object(s3_sink, "flush") as mock_flush:
            mock_flush.return_value = True

            await s3_sink.close()

            mock_flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_multiple_events_processing(self, s3_sink):
        """Test processing multiple events from different parsers."""
        events = []
        for i in range(5):
            events.append({
                "_metadata": {"parser_id": f"parser_{i % 2}"},
                "log": {"class_uid": 2004}
            })

        result = await s3_sink.write_events(events)

        assert result is True

    def test_default_aws_region(self, mock_boto3):
        """Test default AWS region is us-east-1."""
        sink = S3ArchiveSink(bucket_name="test-bucket")

        mock_boto3.client.assert_called_once_with(
            "s3", region_name="us-east-1"
        )

    @pytest.mark.asyncio
    async def test_batch_size_configuration(self, mock_boto3, sample_event):
        """Test batch size is respected."""
        sink = S3ArchiveSink(bucket_name="test-bucket", batch_size=3)

        with patch.object(sink, "flush") as mock_flush:
            mock_flush.return_value = True

            await sink.write_event(sample_event)
            await sink.write_event(sample_event)
            mock_flush.assert_not_called()

            await sink.write_event(sample_event)
            mock_flush.assert_called_once()
