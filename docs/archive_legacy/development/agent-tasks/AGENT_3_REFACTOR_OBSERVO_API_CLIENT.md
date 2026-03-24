# Agent Task 3: Refactor observo_api_client.py into API Module

**Agent Model:** Claude Haiku (fast, efficient)
**Estimated Time:** 90 minutes
**Risk Level:** MEDIUM
**Files Modified:** 1 large file → 7 modular files

---

## Mission Objective

Refactor `components/observo_api_client.py` (875 lines) into smaller, focused modules organized in `components/observo/` directory, grouping related API operations together while maintaining 100% backward compatibility.

**Success Criteria:**
- [ ] Original file reduced to <100 lines (backward compatibility wrapper)
- [ ] 6-7 new focused modules created (~120-150 lines each)
- [ ] All API operations still work
- [ ] All async methods preserved
- [ ] Error handling intact
- [ ] Statistics tracking works
- [ ] Zero syntax errors
- [ ] Zero functional regressions

---

## Current File Analysis

**File:** `components/observo_api_client.py`
**Lines:** 875
**Main Classes:**
- `ObservoAPIError` (Exception class)
- `ObservoAPI` (Main API client)

**API Method Categories:**
1. **Core HTTP** (~100 lines): `__init__`, `_request`, context managers
2. **Pipeline Operations** (~150 lines): add, update, delete, list, deploy, pause, resume
3. **Source Operations** (~120 lines): add, update, delete, list, templates
4. **Sink Operations** (~120 lines): add, update, delete, list, templates
5. **Transform Operations** (~120 lines): add, update, delete, list, templates
6. **Site Operations** (~60 lines): list, get
7. **Monitoring Operations** (~100 lines): metrics, health check, statistics

**Dependencies:**
```python
import aiohttp
import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import json
from .observo_models import (Pipeline, Source, Sink, Transform, ...)
```

---

## Target Architecture

Create this directory structure:

```
components/observo/
├── __init__.py          # Public interface (backward compatibility)
├── client.py            # Main API client class (~150 lines)
├── pipelines.py         # Pipeline API operations (~150 lines)
├── sources.py           # Source API operations (~120 lines)
├── sinks.py             # Sink API operations (~120 lines)
├── transforms.py        # Transform API operations (~120 lines)
├── monitoring.py        # Monitoring, metrics, health (~100 lines)
└── exceptions.py        # Custom exceptions (~30 lines)
```

---

## Step-by-Step Execution Plan

### STEP 1: Create Directory and Exceptions

**Action:**
```bash
mkdir -p components/observo
```

**Create:** `components/observo/exceptions.py`
```python
"""Custom exceptions for Observo API client."""


class ObservoAPIError(Exception):
    """Base exception for Observo API errors."""
    pass


class ObservoConnectionError(ObservoAPIError):
    """Connection error to Observo API."""
    pass


class ObservoAuthenticationError(ObservoAPIError):
    """Authentication error with Observo API."""
    pass


class ObservoValidationError(ObservoAPIError):
    """Validation error for API requests."""
    pass
```

---

### STEP 2: Create Base Client (client.py)

**Create:** `components/observo/client.py`

**Content to Extract:**
- Class definition
- `__init__` method
- `__aenter__` and `__aexit__` methods
- `_request` method
- `get_statistics` method
- `reset_statistics` method

**Code:**
```python
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
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path
            data: Request body data (for POST/PUT)
            params: Query parameters

        Returns:
            Response data as dictionary

        Raises:
            ObservoAPIError: If request fails after retries
        """
        # [COPY ENTIRE _request IMPLEMENTATION FROM observo_api_client.py:96-172]
        pass  # Replace with full implementation

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
        return {
            **self.statistics,
            "success_rate": (
                self.statistics["requests_successful"] / self.statistics["requests_sent"]
                if self.statistics["requests_sent"] > 0
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
```

---

### STEP 3: Extract Pipeline Operations (pipelines.py)

**Create:** `components/observo/pipelines.py`

**Content to Extract:**
- `add_pipeline` method
- `update_pipeline` method
- `delete_pipeline` method
- `get_pipeline` method
- `list_pipelines` method
- `deploy_pipeline` method
- `get_pipeline_status` method
- `pause_pipeline` method
- `resume_pipeline` method

**Code:**
```python
"""Pipeline API operations for Observo.ai."""

import logging
from typing import Dict, List, Optional, Any

try:
    from .observo_models import Pipeline, PipelineStatus
except ImportError:
    from components.observo_models import Pipeline, PipelineStatus

logger = logging.getLogger(__name__)


class PipelineOperations:
    """Pipeline management operations for Observo API."""

    async def add_pipeline(self, pipeline: Pipeline) -> Dict[str, Any]:
        """
        Create a new pipeline.

        Args:
            pipeline: Pipeline object to create

        Returns:
            API response with pipeline details
        """
        # [COPY IMPLEMENTATION FROM observo_api_client.py:173-189]
        pass

    async def update_pipeline(self, pipeline: Pipeline, last_updated: str) -> Dict[str, Any]:
        """
        Update an existing pipeline.

        Args:
            pipeline: Pipeline object with updates
            last_updated: Last updated timestamp for concurrency control

        Returns:
            API response with updated pipeline
        """
        # [COPY IMPLEMENTATION FROM observo_api_client.py:190-207]
        pass

    async def delete_pipeline(self, pipeline_id: int) -> Dict[str, Any]:
        """
        Delete a pipeline.

        Args:
            pipeline_id: ID of pipeline to delete

        Returns:
            API response
        """
        # [COPY IMPLEMENTATION FROM observo_api_client.py:208-222]
        pass

    async def get_pipeline(self, pipeline_id: int) -> Dict[str, Any]:
        """
        Get pipeline details.

        Args:
            pipeline_id: ID of pipeline to retrieve

        Returns:
            Pipeline details
        """
        # [COPY IMPLEMENTATION FROM observo_api_client.py:223-237]
        pass

    async def list_pipelines(
        self,
        page: int = 1,
        page_size: int = 100,
        status: Optional[PipelineStatus] = None,
        name_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List pipelines with pagination and filtering.

        Args:
            page: Page number
            page_size: Number of items per page
            status: Filter by pipeline status
            name_filter: Filter by pipeline name

        Returns:
            List of pipelines with pagination info
        """
        # [COPY IMPLEMENTATION FROM observo_api_client.py:238-275]
        pass

    async def deploy_pipeline(
        self,
        pipeline_id: int,
        site_ids: List[int],
        auto_start: bool = True
    ) -> Dict[str, Any]:
        """
        Deploy pipeline to sites.

        Args:
            pipeline_id: ID of pipeline to deploy
            site_ids: List of site IDs to deploy to
            auto_start: Whether to start pipeline after deployment

        Returns:
            Deployment result
        """
        # [COPY IMPLEMENTATION FROM observo_api_client.py:276-317]
        pass

    async def get_pipeline_status(self, pipeline_id: int) -> Dict[str, Any]:
        """
        Get pipeline runtime status.

        Args:
            pipeline_id: ID of pipeline

        Returns:
            Pipeline status details
        """
        # [COPY IMPLEMENTATION FROM observo_api_client.py:318-332]
        pass

    async def pause_pipeline(self, pipeline_id: int) -> Dict[str, Any]:
        """
        Pause a running pipeline.

        Args:
            pipeline_id: ID of pipeline to pause

        Returns:
            API response
        """
        # [COPY IMPLEMENTATION FROM observo_api_client.py:333-347]
        pass

    async def resume_pipeline(self, pipeline_id: int) -> Dict[str, Any]:
        """
        Resume a paused pipeline.

        Args:
            pipeline_id: ID of pipeline to resume

        Returns:
            API response
        """
        # [COPY IMPLEMENTATION FROM observo_api_client.py:348-366]
        pass
```

---

### STEP 4: Extract Source Operations (sources.py)

**Create:** `components/observo/sources.py`

**Content to Extract:**
- `add_source` method
- `update_source` method
- `delete_source` method
- `list_sources` method
- `list_source_templates` method

**Code:**
```python
"""Source API operations for Observo.ai."""

import logging
from typing import Dict, List, Optional, Any

try:
    from .observo_models import Source, SourceType
except ImportError:
    from components.observo_models import Source, SourceType

logger = logging.getLogger(__name__)


class SourceOperations:
    """Source management operations for Observo API."""

    async def add_source(self, source: Source) -> Dict[str, Any]:
        """Create a new source."""
        # [COPY IMPLEMENTATION FROM observo_api_client.py:367-383]
        pass

    async def update_source(self, source: Source, last_updated: str) -> Dict[str, Any]:
        """Update an existing source."""
        # [COPY IMPLEMENTATION FROM observo_api_client.py:384-400]
        pass

    async def delete_source(self, source_id: int) -> Dict[str, Any]:
        """Delete a source."""
        # [COPY IMPLEMENTATION FROM observo_api_client.py:401-415]
        pass

    async def list_sources(
        self,
        page: int = 1,
        page_size: int = 100,
        source_type: Optional[SourceType] = None
    ) -> Dict[str, Any]:
        """List sources with pagination."""
        # [COPY IMPLEMENTATION FROM observo_api_client.py:416-456]
        pass

    async def list_source_templates(
        self,
        source_type: Optional[SourceType] = None
    ) -> Dict[str, Any]:
        """List available source templates."""
        # [COPY IMPLEMENTATION FROM observo_api_client.py:457-485]
        pass
```

---

### STEP 5: Extract Sink Operations (sinks.py)

**Create:** `components/observo/sinks.py`

**Content to Extract:**
- `add_sink` method
- `update_sink` method
- `delete_sink` method
- `list_sinks` method
- `list_sink_templates` method

**Code:**
```python
"""Sink API operations for Observo.ai."""

import logging
from typing import Dict, List, Optional, Any

try:
    from .observo_models import Sink, SinkType
except ImportError:
    from components.observo_models import Sink, SinkType

logger = logging.getLogger(__name__)


class SinkOperations:
    """Sink management operations for Observo API."""

    async def add_sink(self, sink: Sink) -> Dict[str, Any]:
        """Create a new sink."""
        # [COPY IMPLEMENTATION FROM observo_api_client.py:486-502]
        pass

    async def update_sink(self, sink: Sink, last_updated: str) -> Dict[str, Any]:
        """Update an existing sink."""
        # [COPY IMPLEMENTATION FROM observo_api_client.py:503-519]
        pass

    async def delete_sink(self, sink_id: int) -> Dict[str, Any]:
        """Delete a sink."""
        # [COPY IMPLEMENTATION FROM observo_api_client.py:520-534]
        pass

    async def list_sinks(
        self,
        page: int = 1,
        page_size: int = 100,
        sink_type: Optional[SinkType] = None
    ) -> Dict[str, Any]:
        """List sinks with pagination."""
        # [COPY IMPLEMENTATION FROM observo_api_client.py:535-575]
        pass

    async def list_sink_templates(
        self,
        sink_type: Optional[SinkType] = None
    ) -> Dict[str, Any]:
        """List available sink templates."""
        # [COPY IMPLEMENTATION FROM observo_api_client.py:576-604]
        pass
```

---

### STEP 6: Extract Transform Operations (transforms.py)

**Create:** `components/observo/transforms.py`

**Content to Extract:**
- `add_transform` method
- `update_transform` method
- `delete_transform` method
- `list_transforms` method
- `list_transform_templates` method

**Code:**
```python
"""Transform API operations for Observo.ai."""

import logging
from typing import Dict, List, Optional, Any

try:
    from .observo_models import Transform
except ImportError:
    from components.observo_models import Transform

logger = logging.getLogger(__name__)


class TransformOperations:
    """Transform management operations for Observo API."""

    async def add_transform(self, transform: Transform) -> Dict[str, Any]:
        """Create a new transform."""
        # [COPY IMPLEMENTATION FROM observo_api_client.py:605-621]
        pass

    async def update_transform(self, transform: Transform, last_updated: str) -> Dict[str, Any]:
        """Update an existing transform."""
        # [COPY IMPLEMENTATION FROM observo_api_client.py:622-638]
        pass

    async def delete_transform(self, transform_id: int) -> Dict[str, Any]:
        """Delete a transform."""
        # [COPY IMPLEMENTATION FROM observo_api_client.py:639-653]
        pass

    async def list_transforms(
        self,
        page: int = 1,
        page_size: int = 100,
        name_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """List transforms with pagination."""
        # [COPY IMPLEMENTATION FROM observo_api_client.py:654-698]
        pass

    async def list_transform_templates(self) -> Dict[str, Any]:
        """List available transform templates."""
        # [COPY IMPLEMENTATION FROM observo_api_client.py:699-727]
        pass
```

---

### STEP 7: Extract Monitoring Operations (monitoring.py)

**Create:** `components/observo/monitoring.py`

**Content to Extract:**
- `list_sites` method
- `get_site` method
- `get_pipeline_metrics` method
- `get_source_metrics` method
- `health_check` method

**Code:**
```python
"""Monitoring and health check operations for Observo.ai."""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class MonitoringOperations:
    """Monitoring, metrics, and health operations for Observo API."""

    async def list_sites(
        self,
        page: int = 1,
        page_size: int = 100
    ) -> Dict[str, Any]:
        """List available sites."""
        # [COPY IMPLEMENTATION FROM observo_api_client.py:728-758]
        pass

    async def get_site(self, site_id: int) -> Dict[str, Any]:
        """Get site details."""
        # [COPY IMPLEMENTATION FROM observo_api_client.py:759-777]
        pass

    async def get_pipeline_metrics(
        self,
        pipeline_id: int,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get pipeline metrics."""
        # [COPY IMPLEMENTATION FROM observo_api_client.py:778-806]
        pass

    async def get_source_metrics(
        self,
        source_id: int,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get source metrics."""
        # [COPY IMPLEMENTATION FROM observo_api_client.py:807-835]
        pass

    async def health_check(self) -> Dict[str, Any]:
        """Check API health status."""
        # [COPY IMPLEMENTATION FROM observo_api_client.py:836-851]
        pass
```

---

### STEP 8: Create Unified API Class (__init__.py)

**Create:** `components/observo/__init__.py`

**Code:**
```python
"""
Observo.ai API Client Module.

Provides complete REST API integration for Observo.ai platform.
Refactored from observo_api_client.py for better organization.
"""

from .exceptions import ObservoAPIError, ObservoConnectionError, ObservoAuthenticationError
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
    - Pipelines: Create, update, delete, list, deploy
    - Sources: Create, update, delete, list, templates
    - Sinks: Create, update, delete, list, templates
    - Transforms: Create, update, delete, list, templates
    - Sites: List, create, update, delete
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
        # Initialize base client
        ObservoAPIClient.__init__(self, api_key, base_url, timeout, max_retries)


__all__ = [
    'ObservoAPI',
    'ObservoAPIError',
    'ObservoConnectionError',
    'ObservoAuthenticationError',
]
```

---

### STEP 9: Update Original File to Wrapper

**Modify:** `components/observo_api_client.py`

Replace entire content with:

```python
"""
Observo.ai API Client - Backward Compatibility Wrapper

DEPRECATED: This file now imports from components.observo module.
For new code, import directly from components.observo:
    from components.observo import ObservoAPI

This wrapper maintains backward compatibility with existing code.
"""

from components.observo import ObservoAPI, ObservoAPIError

__all__ = ['ObservoAPI', 'ObservoAPIError']
```

---

## Verification Checklist

### 1. File Structure Check
```bash
ls -la components/observo/
# Should show all 8 module files
```

### 2. Import Verification
```python
from components.observo import ObservoAPI  # New path
from components.observo_api_client import ObservoAPI  # Old path (should still work)
print("✓ Imports successful")
```

### 3. Syntax Check
```bash
python -m py_compile components/observo/*.py
```

### 4. API Client Test
```python
from components.observo import ObservoAPI
client = ObservoAPI(api_key="test-key")
# Should create instance without errors
```

---

## Rollback Instructions

```bash
git checkout -- components/observo_api_client.py
rm -rf components/observo/
```

---

## Success Criteria

- [ ] All 8 modules created in `components/observo/`
- [ ] Original file reduced to <50 lines
- [ ] No syntax errors
- [ ] All async methods preserved
- [ ] Multiple inheritance works correctly
- [ ] Backward compatibility maintained
- [ ] All API operations accessible

---

**EXECUTION COMMAND FOR HAIKU AGENT:**
```
Read this file completely, execute all steps sequentially, verify at each checkpoint, and report status.
```

**END OF AGENT 3 PROMPT**
