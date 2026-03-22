"""Sink API operations for Observo.ai."""

import logging
from typing import Dict, List, Optional, Any

try:
    from ..observo_models import Sink, SinkType, AddSinkRequest
except ImportError:
    from components.observo_models import Sink, SinkType, AddSinkRequest

logger = logging.getLogger(__name__)


class SinkOperations:
    """Sink management operations for Observo API."""

    async def add_sink(self, sink: Sink) -> Dict[str, Any]:
        """
        Create new sink

        Args:
            sink: Sink configuration

        Returns:
            Created sink with ID
        """
        request = AddSinkRequest(sink=sink)
        return await self._request(
            "POST",
            "/gateway/v1/sink",
            data=request.to_dict()
        )

    async def update_sink(self, sink: Sink, last_updated: str) -> Dict[str, Any]:
        """
        Update existing sink

        Args:
            sink: Sink configuration with ID
            last_updated: Last update timestamp

        Returns:
            Updated sink
        """
        return await self._request(
            "PATCH",
            "/gateway/v1/sink",
            data={"sink": sink.to_dict(), "lastUpdated": last_updated}
        )

    async def delete_sink(self, sink_id: int) -> Dict[str, Any]:
        """
        Delete sink

        Args:
            sink_id: Sink ID

        Returns:
            Deletion status
        """
        return await self._request(
            "DELETE",
            f"/gateway/v1/sink/{sink_id}"
        )

    async def list_sinks(
        self,
        site_ids: List[int],
        sink_ids: Optional[List[int]] = None,
        statuses: Optional[List[str]] = None,
        include_config: bool = True,
        offset: int = 0,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        List sinks with filters

        Args:
            site_ids: Filter by site IDs
            sink_ids: Filter by sink IDs
            statuses: Filter by sink statuses
            include_config: Include sink configuration
            offset: Pagination offset
            limit: Pagination limit

        Returns:
            List of sinks
        """
        params = {
            "siteIds": site_ids,
            "includeConfig": include_config,
            "pagination.offset": offset,
            "pagination.limit": limit
        }

        if sink_ids:
            params["sinkIds"] = sink_ids
        if statuses:
            params["statuses"] = statuses

        return await self._request(
            "GET",
            "/gateway/v1/sinks",
            params=params
        )

    async def list_sink_templates(
        self,
        include_config_format: bool = True,
        types: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        List available sink templates

        Args:
            include_config_format: Include configuration format
            types: Filter by sink types

        Returns:
            List of sink templates
        """
        params = {"includeConfigFormat": include_config_format}
        if types:
            params["types"] = types

        return await self._request(
            "GET",
            "/gateway/v1/sink-templates",
            params=params
        )
