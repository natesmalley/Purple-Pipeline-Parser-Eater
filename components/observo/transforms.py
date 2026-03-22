"""Transform API operations for Observo.ai."""

import logging
from typing import Dict, List, Optional, Any

try:
    from ..observo_models import Transform, AddTransformRequest
except ImportError:
    from components.observo_models import Transform, AddTransformRequest

logger = logging.getLogger(__name__)


class TransformOperations:
    """Transform management operations for Observo API."""

    async def add_transform(self, transform: Transform) -> Dict[str, Any]:
        """
        Create new transform

        Args:
            transform: Transform configuration

        Returns:
            Created transform with ID
        """
        request = AddTransformRequest(transform=transform)
        return await self._request(
            "POST",
            "/gateway/v1/transform",
            data=request.to_dict()
        )

    async def update_transform(self, transform: Transform, last_updated: str) -> Dict[str, Any]:
        """
        Update existing transform

        Args:
            transform: Transform configuration with ID
            last_updated: Last update timestamp

        Returns:
            Updated transform
        """
        return await self._request(
            "PATCH",
            "/gateway/v1/transform",
            data={"transform": transform.to_dict(), "lastUpdated": last_updated}
        )

    async def delete_transform(self, transform_id: int) -> Dict[str, Any]:
        """
        Delete transform

        Args:
            transform_id: Transform ID

        Returns:
            Deletion status
        """
        return await self._request(
            "DELETE",
            f"/gateway/v1/transform/{transform_id}"
        )

    async def list_transforms(
        self,
        site_ids: List[int],
        transform_ids: Optional[List[int]] = None,
        pipeline_ids: Optional[List[int]] = None,
        statuses: Optional[List[str]] = None,
        include_config: bool = True,
        offset: int = 0,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        List transforms with filters

        Args:
            site_ids: Filter by site IDs
            transform_ids: Filter by transform IDs
            pipeline_ids: Filter by pipeline IDs
            statuses: Filter by transform statuses
            include_config: Include transform configuration
            offset: Pagination offset
            limit: Pagination limit

        Returns:
            List of transforms
        """
        params = {
            "siteIds": site_ids,
            "includeConfig": include_config,
            "pagination.offset": offset,
            "pagination.limit": limit
        }

        if transform_ids:
            params["transformIds"] = transform_ids
        if pipeline_ids:
            params["pipelineIds"] = pipeline_ids
        if statuses:
            params["statuses"] = statuses

        return await self._request(
            "GET",
            "/gateway/v1/transforms",
            params=params
        )

    async def list_transform_templates(
        self,
        include_config_format: bool = True,
        categories: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        List available transform templates

        Args:
            include_config_format: Include configuration format
            categories: Filter by transform categories

        Returns:
            List of transform templates
        """
        params = {"includeConfigFormat": include_config_format}
        if categories:
            params["categories"] = categories

        return await self._request(
            "GET",
            "/gateway/v1/transform-templates",
            params=params
        )
