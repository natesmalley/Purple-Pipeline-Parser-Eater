"""Monitoring and health check operations for Observo.ai."""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class MonitoringOperations:
    """Monitoring, metrics, and health operations for Observo API."""

    async def list_sites(
        self,
        site_ids: Optional[List[int]] = None,
        offset: int = 0,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        List sites

        Args:
            site_ids: Filter by site IDs
            offset: Pagination offset
            limit: Pagination limit

        Returns:
            List of sites
        """
        params = {
            "pagination.offset": offset,
            "pagination.limit": limit
        }

        if site_ids:
            params["siteIds"] = site_ids

        return await self._request(
            "GET",
            "/gateway/v1/sites",
            params=params
        )

    async def get_site(self, site_id: int) -> Dict[str, Any]:
        """
        Get site by ID

        Args:
            site_id: Site ID

        Returns:
            Site configuration
        """
        return await self._request(
            "GET",
            f"/gateway/v1/site/{site_id}"
        )

    async def get_pipeline_metrics(
        self,
        pipeline_id: int,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get pipeline metrics

        Args:
            pipeline_id: Pipeline ID
            start_time: Start time (ISO format)
            end_time: End time (ISO format)

        Returns:
            Pipeline metrics data
        """
        params = {}
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time

        return await self._request(
            "GET",
            f"/gateway/v1/pipeline/{pipeline_id}/metrics",
            params=params
        )

    async def get_source_metrics(
        self,
        source_id: int,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get source metrics

        Args:
            source_id: Source ID
            start_time: Start time (ISO format)
            end_time: End time (ISO format)

        Returns:
            Source metrics data
        """
        params = {}
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time

        return await self._request(
            "GET",
            f"/gateway/v1/source/{source_id}/metrics",
            params=params
        )

    async def health_check(self) -> Dict[str, Any]:
        """
        Check API health

        Returns:
            Health status
        """
        return await self._request(
            "GET",
            "/health"
        )
