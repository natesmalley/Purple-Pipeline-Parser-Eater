"""
Observo.ai API Client Module.

Provides complete REST API integration for Observo.ai platform.
Refactored from observo_api_client.py for better organization.
"""

from .exceptions import (
    ObservoAPIError,
    ObservoConnectionError,
    ObservoAuthenticationError,
    ObservoValidationError
)
from .client import ObservoAPIClient
from .pipelines import PipelineOperations
from .sources import SourceOperations
from .sinks import SinkOperations
from .transforms import TransformOperations
from .monitoring import MonitoringOperations


class ObservoAPI(
    ObservoAPIClient,
    PipelineOperations,
    SourceOperations,
    SinkOperations,
    TransformOperations,
    MonitoringOperations
):
    """
    Complete Observo.ai REST API client.

    Combines all API operations into a single interface through multiple inheritance.
    Supports all Observo API endpoints:
    - Pipelines: Create, update, delete, list, deploy, pause, resume
    - Sources: Create, update, delete, list, templates
    - Sinks: Create, update, delete, list, templates
    - Transforms: Create, update, delete, list, templates
    - Sites: List, get
    - Monitoring: Pipeline status, metrics, health
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://p01-api.observo.ai",
        timeout: int = 300,
        max_retries: int = 3
    ):
        """
        Initialize Observo API client with all operations.

        Args:
            api_key: Observo API key
            base_url: Observo API base URL
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries for failed requests
        """
        # Initialize base client (which initializes all instance variables)
        ObservoAPIClient.__init__(self, api_key, base_url, timeout, max_retries)


__all__ = [
    'ObservoAPI',
    'ObservoAPIError',
    'ObservoConnectionError',
    'ObservoAuthenticationError',
    'ObservoValidationError',
]
