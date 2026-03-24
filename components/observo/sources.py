"""Source API operations for Observo.ai."""

import logging
from typing import Dict, List, Optional, Any

try:
    from ..observo_models import Source, SourceType, AddSourceRequest
except ImportError:
    from components.observo_models import Source, SourceType, AddSourceRequest

logger = logging.getLogger(__name__)


class SourceOperations:
    """Source management operations for Observo API."""

    async def add_source(self, source: Source) -> Dict[str, Any]:
        """
        Create new source

        Args:
            source: Source configuration

        Returns:
            Created source with ID
        """
        request = AddSourceRequest(source=source)
        return await self._request(
            "POST",
            "/gateway/v1/source",
            data=request.to_dict()
        )

    async def update_source(self, source: Source, last_updated: str) -> Dict[str, Any]:
        """
        Update existing source

        Args:
            source: Source configuration with ID
            last_updated: Last update timestamp

        Returns:
            Updated source
        """
        return await self._request(
            "PATCH",
            "/gateway/v1/source",
            data={"source": source.to_dict(), "lastUpdated": last_updated}
        )

    async def delete_source(self, source_id: int) -> Dict[str, Any]:
        """
        Delete source

        Args:
            source_id: Source ID

        Returns:
            Deletion status
        """
        return await self._request(
            "DELETE",
            f"/gateway/v1/source/{source_id}"
        )

    async def list_sources(
        self,
        site_ids: List[int],
        source_ids: Optional[List[int]] = None,
        statuses: Optional[List[str]] = None,
        include_config: bool = True,
        offset: int = 0,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        List sources with filters

        Args:
            site_ids: Filter by site IDs
            source_ids: Filter by source IDs
            statuses: Filter by source statuses
            include_config: Include source configuration
            offset: Pagination offset
            limit: Pagination limit

        Returns:
            List of sources
        """
        params = {
            "siteIds": site_ids,
            "includeConfig": include_config,
            "pagination.offset": offset,
            "pagination.limit": limit
        }

        if source_ids:
            params["sourceIds"] = source_ids
        if statuses:
            params["statuses"] = statuses

        return await self._request(
            "GET",
            "/gateway/v1/sources",
            params=params
        )

    async def list_source_templates(
        self,
        include_config_format: bool = True,
        types: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        List available source templates

        Args:
            include_config_format: Include configuration format
            types: Filter by source types

        Returns:
            List of source templates
        """
        params = {"includeConfigFormat": include_config_format}
        if types:
            params["types"] = types

        return await self._request(
            "GET",
            "/gateway/v1/source-templates",
            params=params
        )
