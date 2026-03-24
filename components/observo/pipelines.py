"""Pipeline API operations for Observo.ai."""

import logging
from typing import Dict, List, Optional, Any

try:
    from ..observo_models import (
        Pipeline, PipelineGraph, Source, Sink, Transform,
        PipelineStatus, AddPipelineRequest, UpdatePipelineRequest,
        DeserializePipelineRequest
    )
except ImportError:
    from components.observo_models import (
        Pipeline, PipelineGraph, Source, Sink, Transform,
        PipelineStatus, AddPipelineRequest, UpdatePipelineRequest,
        DeserializePipelineRequest
    )

logger = logging.getLogger(__name__)


class PipelineOperations:
    """Pipeline management operations for Observo API."""

    async def add_pipeline(self, pipeline: Pipeline) -> Dict[str, Any]:
        """
        Create new pipeline

        Args:
            pipeline: Pipeline configuration

        Returns:
            Created pipeline with ID and metadata
        """
        request = AddPipelineRequest(pipeline=pipeline)
        return await self._request(
            "POST",
            "/gateway/v1/pipeline",
            data=request.to_dict()
        )

    async def update_pipeline(self, pipeline: Pipeline, last_updated: str) -> Dict[str, Any]:
        """
        Update existing pipeline

        Args:
            pipeline: Pipeline configuration with ID
            last_updated: Last update timestamp for conflict detection

        Returns:
            Updated pipeline
        """
        request = UpdatePipelineRequest(pipeline=pipeline, lastUpdated=last_updated)
        return await self._request(
            "PATCH",
            "/gateway/v1/pipeline",
            data=request.to_dict()
        )

    async def delete_pipeline(self, pipeline_id: int) -> Dict[str, Any]:
        """
        Delete pipeline

        Args:
            pipeline_id: Pipeline ID

        Returns:
            Deletion status
        """
        return await self._request(
            "DELETE",
            f"/gateway/v1/pipeline/{pipeline_id}"
        )

    async def get_pipeline(self, pipeline_id: int) -> Dict[str, Any]:
        """
        Get pipeline by ID

        Args:
            pipeline_id: Pipeline ID

        Returns:
            Pipeline configuration
        """
        return await self._request(
            "GET",
            f"/gateway/v1/pipeline/{pipeline_id}"
        )

    async def list_pipelines(
        self,
        site_ids: List[int],
        pipeline_ids: Optional[List[int]] = None,
        statuses: Optional[List[str]] = None,
        offset: int = 0,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        List pipelines with filters

        Args:
            site_ids: Filter by site IDs
            pipeline_ids: Filter by pipeline IDs
            statuses: Filter by pipeline statuses
            offset: Pagination offset
            limit: Pagination limit

        Returns:
            List of pipelines with pagination
        """
        params = {
            "siteIds": site_ids,
            "pagination.offset": offset,
            "pagination.limit": limit
        }

        if pipeline_ids:
            params["pipelineIds"] = pipeline_ids
        if statuses:
            params["statuses"] = statuses

        return await self._request(
            "GET",
            "/gateway/v1/pipelines",
            params=params
        )

    async def deploy_pipeline(
        self,
        site_id: int,
        pipeline: Pipeline,
        pipeline_graph: PipelineGraph,
        source: Source,
        destinations: List[Sink],
        transforms: List[Transform],
        archival_destination: Optional[Sink] = None
    ) -> Dict[str, Any]:
        """
        Deploy complete pipeline with all components

        Args:
            site_id: Site ID
            pipeline: Pipeline configuration
            pipeline_graph: Pipeline graph structure
            source: Source configuration
            destinations: List of sink configurations
            transforms: List of transform configurations
            archival_destination: Optional archival sink

        Returns:
            Deployed pipeline details
        """
        request = DeserializePipelineRequest(
            siteId=site_id,
            pipeline=pipeline,
            pipelineGraph=pipeline_graph,
            source=source,
            destinations=destinations,
            transforms=transforms,
            archivalDestination=archival_destination,
            deployPipeline=True
        )

        return await self._request(
            "POST",
            "/gateway/v1/deserialize-pipeline",
            data=request.to_dict()
        )

    async def get_pipeline_status(self, pipeline_id: int) -> Dict[str, Any]:
        """
        Get pipeline deployment status

        Args:
            pipeline_id: Pipeline ID

        Returns:
            Pipeline status and metrics
        """
        return await self._request(
            "GET",
            f"/gateway/v1/pipeline/{pipeline_id}/status"
        )

    async def pause_pipeline(self, pipeline_id: int) -> Dict[str, Any]:
        """
        Pause pipeline execution

        Args:
            pipeline_id: Pipeline ID

        Returns:
            Updated pipeline status
        """
        return await self._request(
            "POST",
            f"/gateway/v1/pipeline/{pipeline_id}/pause"
        )

    async def resume_pipeline(self, pipeline_id: int) -> Dict[str, Any]:
        """
        Resume paused pipeline

        Args:
            pipeline_id: Pipeline ID

        Returns:
            Updated pipeline status
        """
        return await self._request(
            "POST",
            f"/gateway/v1/pipeline/{pipeline_id}/resume"
        )
