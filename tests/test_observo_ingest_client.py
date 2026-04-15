"""Unit tests for ObservoIngestClient."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from components.observo_ingest_client import ObservoIngestClient


@pytest.fixture
def observo_client():
    """Create ObservoIngestClient instance."""
    return ObservoIngestClient(
        base_url="https://api.observo.ai",
        api_token="test-token",
        source_name="test-pipeline",
        timeout=30,
        max_batch_size=100,
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
            "metadata": {
                "version": "1.5.0",
                "product": {
                    "name": "Netskope",
                    "vendor_name": "Netskope"
                }
            }
        }
    }


class TestObservoIngestClient:
    """Test ObservoIngestClient class."""

    def test_initialization(self, observo_client):
        """Test client initializes correctly."""
        assert observo_client.base_url == "https://api.observo.ai"
        assert observo_client.api_token == "test-token"
        assert observo_client.source_name == "test-pipeline"
        assert observo_client.timeout == 30
        assert observo_client.max_batch_size == 100

    def test_base_url_strip_trailing_slash(self):
        """Test base URL strips trailing slash."""
        client = ObservoIngestClient(
            base_url="https://api.observo.ai/",
            api_token="token",
        )
        assert client.base_url == "https://api.observo.ai"

    @pytest.mark.asyncio
    async def test_ingest_events_empty_list(self, observo_client):
        """Test ingest_events with empty list returns zeros."""
        result = await observo_client.ingest_events([])
        assert result["accepted"] == 0
        assert result["rejected"] == 0

    @pytest.mark.asyncio
    async def test_ingest_events_single_event(self, observo_client, sample_event):
        """Test ingest_events with single event."""
        with patch.object(observo_client, "_send_batch", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = {"accepted": 1, "rejected": 0}

            result = await observo_client.ingest_events([sample_event])

            assert result["accepted"] == 1
            assert result["rejected"] == 0
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_ingest_events_batching(self, observo_client, sample_event):
        """Test ingest_events batches events correctly."""
        client = ObservoIngestClient(
            base_url="https://api.observo.ai",
            api_token="test-token",
            max_batch_size=2,
        )

        events = [sample_event] * 5

        with patch.object(client, "_send_batch", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = {"accepted": 2, "rejected": 0}

            await client.ingest_events(events)

            assert mock_send.call_count == 3  # 2 + 2 + 1

    @pytest.mark.asyncio
    async def test_ingest_events_with_dataset(self, observo_client, sample_event):
        """Test ingest_events with explicit dataset."""
        with patch.object(observo_client, "_send_batch", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = {"accepted": 1, "rejected": 0}

            await observo_client.ingest_events([sample_event], dataset="custom_dataset")

            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert call_args is not None

    # Batch 3 Stream D fix — all six tests below were written against an
    # aiohttp-style client where `session.post(...)` returns an async
    # context manager and the response is retrieved via
    # `__aenter__`. `components/observo_ingest_client.py` uses httpx:
    # `response = await self.client.post(...)` returns a Response
    # directly, then `response.raise_for_status()` and `.json()` are
    # called synchronously. The old mocks set
    # `mock_post.return_value.__aenter__.return_value = response`,
    # which made `await self.client.post(...)` resolve to a Mock whose
    # `.raise_for_status` was a non-awaited coroutine (hence the
    # `'coroutine' object has no attribute 'get'` and `DID NOT RAISE`
    # symptoms). New mocks set `mock_post.return_value = mock_response`
    # directly and use a sync MagicMock for the response so
    # `raise_for_status` and `json` are callable sync.

    @staticmethod
    def _make_response(*, status_code: int = 200, payload=None, text: str = "") -> MagicMock:
        """Build an httpx-shaped response mock (sync methods)."""
        response = MagicMock()
        response.status_code = status_code
        response.text = text
        if payload is not None:
            response.json.return_value = payload
        return response

    @pytest.mark.asyncio
    async def test_send_batch_with_log_wrapper(self, observo_client, sample_event):
        """Test _send_batch extracts OCSF log correctly."""
        with patch.object(observo_client.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = self._make_response(
                payload={"accepted": 1, "rejected": 0},
            )

            result = await observo_client._send_batch([sample_event])

            assert result["accepted"] == 1
            mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_batch_without_log_wrapper(self, observo_client, valid_ocsf_event):
        """Test _send_batch handles events without log wrapper."""
        with patch.object(observo_client.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = self._make_response(
                payload={"accepted": 1, "rejected": 0},
            )

            result = await observo_client._send_batch([valid_ocsf_event])

            assert result["accepted"] == 1

    @pytest.mark.asyncio
    async def test_send_batch_http_error(self, observo_client, sample_event):
        """Test _send_batch handles HTTP errors."""
        import httpx

        with patch.object(observo_client.client, "post", new_callable=AsyncMock) as mock_post:
            mock_response = self._make_response(
                status_code=500,
                text="Internal Server Error",
            )
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "HTTP 500",
                request=MagicMock(),
                response=mock_response,
            )
            mock_post.return_value = mock_response

            result = await observo_client._send_batch([sample_event])

            assert result["accepted"] == 0
            assert result["rejected"] == 1
            assert "error" in result

    @pytest.mark.asyncio
    async def test_send_batch_request_error(self, observo_client, sample_event):
        """Test _send_batch handles request errors."""
        import httpx

        with patch.object(observo_client.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.RequestError("Connection refused")

            result = await observo_client._send_batch([sample_event])

            assert result["accepted"] == 0
            assert result["rejected"] == 1
            assert "error" in result

    @pytest.mark.asyncio
    async def test_send_batch_updates_stats(self, observo_client, sample_event):
        """Test _send_batch updates statistics."""
        with patch.object(observo_client.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = self._make_response(
                payload={"accepted": 1, "rejected": 0},
            )

            await observo_client._send_batch([sample_event])

            assert observo_client.stats["total_sent"] == 1
            assert observo_client.stats["total_accepted"] == 1

    @pytest.mark.asyncio
    async def test_test_connection_success(self, observo_client):
        """Test test_connection succeeds."""
        with patch.object(observo_client.client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = self._make_response(status_code=200)

            result = await observo_client.test_connection()

            assert result is True

    @pytest.mark.asyncio
    async def test_test_connection_failure(self, observo_client):
        """Test test_connection fails on error."""
        with patch.object(observo_client.client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = Exception("Connection failed")

            result = await observo_client.test_connection()

            assert result is False

    def test_get_statistics(self, observo_client):
        """Test get_statistics returns correct format."""
        observo_client.stats = {
            "total_sent": 100,
            "total_accepted": 95,
            "total_rejected": 5,
            "total_errors": 0,
        }

        stats = observo_client.get_statistics()

        assert stats["total_sent"] == 100
        assert stats["total_accepted"] == 95
        assert stats["success_rate"] == 0.95

    def test_get_statistics_zero_sent(self, observo_client):
        """Test get_statistics with no events sent."""
        stats = observo_client.get_statistics()

        assert stats["total_sent"] == 0
        assert stats["success_rate"] == 0

    @pytest.mark.asyncio
    async def test_close(self, observo_client):
        """Test close closes the HTTP client."""
        with patch.object(observo_client.client, "aclose", new_callable=AsyncMock) as mock_close:
            await observo_client.close()
            mock_close.assert_called_once()


@pytest.fixture
def valid_ocsf_event():
    """Create a valid OCSF event without log wrapper."""
    return {
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
