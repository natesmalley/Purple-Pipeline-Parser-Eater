"""Base Observo API client with HTTP request handling."""

import aiohttp
import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import json

from .exceptions import ObservoAPIError, ObservoConnectionError, ObservoAuthenticationError

logger = logging.getLogger(__name__)


class ObservoAPIClient:
    """
    Base Observo.ai REST API client.

    Provides HTTP request handling and session management.
    Specific API operations are in separate modules.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://p01-api.observo.ai",
        timeout: int = 300,
        max_retries: int = 3
    ):
        """
        Initialize Observo API client.

        Args:
            api_key: Observo API key
            base_url: Observo API base URL
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries for failed requests
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.max_retries = max_retries

        self.headers = {
            "authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Purple-Pipeline-Parser-Eater/10.0.0"
        }

        self.session: Optional[aiohttp.ClientSession] = None
        self.statistics = {
            "requests_sent": 0,
            "requests_successful": 0,
            "requests_failed": 0,
            "errors": []
        }

    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession(headers=self.headers)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make HTTP request to Observo API with retries.

        Args:
            method: HTTP method (GET, POST, PATCH, DELETE)
            endpoint: API endpoint path
            data: Request body data (for POST/PUT)
            params: Query parameters

        Returns:
            Response data as dictionary

        Raises:
            ObservoAPIError: If request fails after retries
        """
        url = f"{self.base_url}{endpoint}"
        self.statistics["requests_sent"] += 1

        for attempt in range(self.max_retries):
            try:
                async with self.session.request(
                    method,
                    url,
                    json=data,
                    params=params,
                    timeout=self.timeout
                ) as response:
                    response_text = await response.text()

                    if response.status in [200, 201]:
                        self.statistics["requests_successful"] += 1
                        try:
                            return json.loads(response_text)
                        except json.JSONDecodeError:
                            return {"status": "ok", "raw_response": response_text}

                    # Handle errors
                    error_msg = f"API request failed with status {response.status}: {response_text}"
                    logger.error(error_msg)

                    if response.status >= 500 and attempt < self.max_retries - 1:
                        # Retry on server errors
                        await asyncio.sleep(2 ** attempt)
                        continue

                    self.statistics["requests_failed"] += 1
                    self.statistics["errors"].append(error_msg)
                    raise ObservoAPIError(error_msg)

            except asyncio.TimeoutError:
                error_msg = f"Request timeout after {self.timeout}s"
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                logger.error(error_msg)
                self.statistics["requests_failed"] += 1
                self.statistics["errors"].append(error_msg)
                raise ObservoAPIError(error_msg)

            except Exception as e:
                error_msg = f"Request failed: {str(e)}"
                logger.error(error_msg)
                self.statistics["requests_failed"] += 1
                self.statistics["errors"].append(error_msg)
                raise ObservoAPIError(error_msg)

    async def close(self):
        """Close the HTTP session."""
        if self.session:
            await self.session.close()
            self.session = None

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get API client statistics.

        Returns:
            Statistics dictionary
        """
        total_requests = self.statistics["requests_sent"]
        return {
            **self.statistics,
            "success_rate": (
                self.statistics["requests_successful"] / total_requests
                if total_requests > 0
                else 0.0
            )
        }

    def reset_statistics(self):
        """Reset statistics counters."""
        self.statistics = {
            "requests_sent": 0,
            "requests_successful": 0,
            "requests_failed": 0,
            "errors": []
        }
        logger.info("Statistics reset")
