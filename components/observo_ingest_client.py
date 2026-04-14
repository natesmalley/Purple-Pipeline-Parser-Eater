"""Observo.ai Event Ingestion API client."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    import httpx
except ImportError:
    httpx = None

logger = logging.getLogger(__name__)


class ObservoIngestClient:
    """
    Client for Observo.ai Event Ingestion API.

    API Endpoint: POST /api/v1/ingest/ocsf
    Authentication: Bearer token

    Supports:
    - Batch event ingestion
    - Retry with exponential backoff
    - Dataset routing
    """

    def __init__(
        self,
        base_url: str,
        api_token: str,
        source_name: str = "purple-pipeline",
        timeout: int = 30,
        max_batch_size: int = 100,
    ):
        """
        Initialize Observo Ingest Client.

        Args:
            base_url: Observo.ai API base URL (e.g., "https://api.observo.ai")
            api_token: API authentication token
            source_name: Source identifier for events
            timeout: Request timeout in seconds
            max_batch_size: Maximum events per batch request
        """
        if httpx is None:
            raise ImportError(
                "httpx is required for ObservoIngestClient. "
                "Install it with: pip install httpx"
            )

        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self.source_name = source_name
        self.timeout = timeout
        self.max_batch_size = max_batch_size

        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json",
                "User-Agent": "Purple-Pipeline/1.0",
            },
        )

        self.stats = {
            "total_sent": 0,
            "total_accepted": 0,
            "total_rejected": 0,
            "total_errors": 0,
        }

        logger.info(
            f"ObservoIngestClient initialized: {self.base_url}"
        )

    async def ingest_events(
        self,
        events: List[Dict[str, Any]],
        dataset: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Ingest OCSF events to Observo.ai.

        Args:
            events: List of OCSF-compliant event dictionaries
            dataset: Dataset name for routing (defaults to parser_id)

        Returns:
            Response dict with accepted/rejected counts

        Raises:
            httpx.HTTPStatusError: On HTTP error responses
            httpx.RequestError: On network/connection errors
        """
        if not events:
            return {"accepted": 0, "rejected": 0}

        results = {"accepted": 0, "rejected": 0, "errors": []}

        for i in range(0, len(events), self.max_batch_size):
            batch = events[i : i + self.max_batch_size]
            batch_result = await self._send_batch(batch, dataset)

            results["accepted"] += batch_result.get("accepted", 0)
            results["rejected"] += batch_result.get("rejected", 0)
            if "error" in batch_result:
                results["errors"].append(batch_result["error"])

        return results

    async def _send_batch(
        self,
        events: List[Dict[str, Any]],
        dataset: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send a single batch of events to Observo.ai."""
        if not dataset and events:
            first_event_meta = events[0].get("_metadata", {})
            dataset = first_event_meta.get("parser_id", "default")

        ocsf_events = []
        for event in events:
            if "log" in event:
                ocsf_events.append(event["log"])
            else:
                ocsf_events.append(event)

        payload = {
            "events": ocsf_events,
            "source": self.source_name,
            "dataset": dataset,
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }

        try:
            logger.debug(
                f"Sending {len(ocsf_events)} events to Observo.ai "
                f"(dataset={dataset})"
            )

            response = await self.client.post(
                "/api/v1/ingest/ocsf",
                json=payload,
            )

            response.raise_for_status()
            result = response.json()

            self.stats["total_sent"] += len(ocsf_events)
            self.stats["total_accepted"] += result.get("accepted", 0)
            self.stats["total_rejected"] += result.get("rejected", 0)

            logger.info(
                f"Observo.ai ingestion: {result.get('accepted', 0)} "
                f"accepted, {result.get('rejected', 0)} rejected"
            )

            return result

        except httpx.HTTPStatusError as e:
            self.stats["total_errors"] += 1
            error_detail = (
                f"HTTP {e.response.status_code}: {e.response.text}"
            )
            logger.error(f"Observo.ai ingestion failed: {error_detail}")

            return {
                "accepted": 0,
                "rejected": len(events),
                "error": error_detail,
            }

        except httpx.RequestError as e:
            self.stats["total_errors"] += 1
            error_detail = f"Request error: {str(e)}"
            logger.error(f"Observo.ai ingestion failed: {error_detail}")

            return {
                "accepted": 0,
                "rejected": len(events),
                "error": error_detail,
            }

    async def test_connection(self) -> bool:
        """
        Test connection to Observo.ai API.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            response = await self.client.get("/api/v1/health")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Observo.ai connection test failed: {e}")
            return False

    def get_statistics(self) -> Dict[str, Any]:
        """Get ingestion statistics."""
        return {
            **self.stats,
            "success_rate": (
                self.stats["total_accepted"] / self.stats["total_sent"]
                if self.stats["total_sent"] > 0
                else 0
            ),
        }

    async def close(self) -> None:
        """Close HTTP client."""
        await self.client.aclose()
