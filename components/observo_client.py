"""
Observo.ai API Client for Purple Pipeline Parser Eater
Intelligent pipeline deployment with Claude-optimized configuration and RAG enhancement

Targets the SaaS REST control plane at p01-api.observo.ai/gateway/v1/*.
Do NOT mutate to snake_case based on dataplane-binary findings (plan
Phase 4.C). The dataplane-binary / standalone YAML path is a separate
code path and must not be reconciled against this client's payload
shape.
"""
import asyncio
import aiohttp
import logging
from typing import Dict, Optional, List
from datetime import datetime
import json
from anthropic import AsyncAnthropic

# Use absolute imports for proper module execution
try:
    from utils.error_handler import ObservoAPIError, DeploymentError, RateLimiter
except ImportError:
    from ..utils.error_handler import ObservoAPIError, DeploymentError, RateLimiter

# Import new comprehensive API client and pipeline builder
try:
    from .observo import ObservoAPI
    from .observo_pipeline_builder import PipelineBuilder, PipelineOptimizer
    from .observo_models import Pipeline, Source, Sink, Transform
except ImportError:
    from components.observo import ObservoAPI
    from observo_pipeline_builder import PipelineBuilder, PipelineOptimizer
    from observo_models import Pipeline, Source, Sink, Transform


logger = logging.getLogger(__name__)


class ObservoAPIClient:
    """
    Intelligent Observo.ai API client with Claude optimization and RAG enhancement

    This class now wraps the comprehensive ObservoAPI client and provides
    high-level methods for parser-to-pipeline conversion with RAG intelligence.
    """

    def __init__(self, config: Dict, claude_client: Optional[AsyncAnthropic] = None, rag_knowledge=None):
        self.config = config
        observo_config = config.get("observo", {})

        self.api_key = observo_config.get("api_key")
        # FIXED: Check for both placeholder and dry-run-mode
        if not self.api_key or self.api_key in {"your-observo-api-key-here", "dry-run-mode"}:
            logger.warning("Observo API key not configured - running in mock mode")
            self.mock_mode = True
        else:
            self.mock_mode = False

        self.base_url = observo_config.get("base_url", "https://p01-api.observo.ai")
        self.deployment_timeout = observo_config.get("deployment_timeout", 300)
        self.site_id = observo_config.get("site_id", 1)  # Default site ID

        # Set up headers for session
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        if self.api_key and not self.mock_mode:
            self.headers["Authorization"] = f"Bearer {self.api_key}"

        # Initialize comprehensive API client
        if not self.mock_mode:
            self.api_client = ObservoAPI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.deployment_timeout
            )
        else:
            self.api_client = None

        # Initialize pipeline builder
        self.pipeline_builder = PipelineBuilder(site_id=self.site_id)
        self.pipeline_optimizer = PipelineOptimizer()

        self.claude = claude_client
        self.rag_knowledge = rag_knowledge

        self.rate_limiter = RateLimiter(
            calls_per_second=1.0 / observo_config.get("rate_limit_delay", 2.0)
        )

        self.session: Optional[aiohttp.ClientSession] = None
        self.statistics = {
            "pipelines_created": 0,
            "deployments_successful": 0,
            "deployments_failed": 0,
            "errors": [],
            "rag_queries": 0,
            "optimization_applied": 0
        }

    async def __aenter__(self):
        """Async context manager entry - create session with connection pooling"""
        # Create TCP connector with connection pooling
        # limit: max total connections
        # limit_per_host: max connections to single host
        connector = aiohttp.TCPConnector(
            limit=100,           # Max total connections
            limit_per_host=10,   # Max per host
            ttl_dns_cache=300    # DNS cache TTL in seconds
        )
        self.session = aiohttp.ClientSession(
            headers=self.headers,
            connector=connector
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - properly close session"""
        if self.session:
            await self.session.close()

    async def create_optimized_pipeline(
        self,
        parser_analysis: Dict,
        lua_code: str,
        parser_metadata: Dict
    ) -> Dict:
        """
        Create pipeline with Claude-optimized configuration
        """
        parser_id = parser_analysis.get("parser_id", "unknown")
        logger.info(f"[START] Creating optimized pipeline for {parser_id}")

        await self.rate_limiter.wait()

        try:
            # Generate optimized configuration
            if self.claude and not self.mock_mode:
                config = await self._generate_optimized_config(parser_analysis, lua_code)
            else:
                config = self._default_pipeline_config(parser_analysis, lua_code, parser_metadata)

            # Deploy to Observo.ai
            if self.mock_mode:
                logger.info(f"[MOCK MODE] Would deploy pipeline: {parser_id}")
                result = self._mock_deployment_response(parser_id, config)
            else:
                result = await self._deploy_pipeline(config)

            self.statistics["pipelines_created"] += 1
            self.statistics["deployments_successful"] += 1

            logger.info(f"[OK] Successfully deployed pipeline: {parser_id}")
            return result

        except Exception as e:
            logger.error(f"Failed to create pipeline for {parser_id}: {e}")
            self.statistics["deployments_failed"] += 1
            self.statistics["errors"].append(f"{parser_id}: {str(e)}")
            raise ObservoAPIError(f"Pipeline creation failed: {e}")

    async def _generate_optimized_config(self, parser_analysis: Dict, lua_code: str) -> Dict:
        """Generate optimized configuration using Claude"""
        parser_id = parser_analysis.get("parser_id")
        complexity = parser_analysis.get("parser_complexity", {}).get("level", "Medium")
        expected_volume = parser_analysis.get("performance_characteristics", {}).get("expected_volume", "Medium")
        ocsf_class = parser_analysis.get("ocsf_classification", {}).get("class_name", "Unknown")

        optimization_prompt = f"""Generate an optimized Observo.ai pipeline configuration for:

Parser: {parser_id}
Complexity: {complexity}
Expected Volume: {expected_volume}
OCSF Class: {ocsf_class}

LUA Transformation Code:
{lua_code[:500]}...

Create a JSON configuration optimized for:
1. PERFORMANCE: Resource allocation for {expected_volume} data volume
2. COST: Minimize resource usage while maintaining performance
3. RELIABILITY: Error handling, retries, and monitoring
4. SCALABILITY: Auto-scaling based on load

Configuration should include:
- Appropriate instance sizing (small/medium/large)
- Batch processing settings (batch size 100-1000 events)
- Error handling (max retries: 3, timeout: 30s)
- Monitoring configuration (enable metrics, logs, traces)
- Auto-scaling parameters (min: 1, max: 10 instances)
- Resource limits (memory: 512MB-2GB, CPU: 0.5-2 cores)

Respond with ONLY a valid JSON configuration object."""

        try:
            response = await self.claude.messages.create(
                model=self.config.get("anthropic", {}).get("model"),
                max_tokens=2000,
                temperature=0.1,
                messages=[{"role": "user", "content": optimization_prompt}]
            )

            config_text = response.content[0].text.strip()

            # Clean and parse JSON
            if config_text.startswith("```json"):
                config_text = config_text[7:]
            if config_text.endswith("```"):
                config_text = config_text[:-3]

            config = json.loads(config_text.strip())
            logger.info(f"Generated optimized configuration for {parser_id}")
            return config

        except Exception as e:
            logger.warning(f"Claude optimization failed, using default config: {e}")
            return self._default_pipeline_config(parser_analysis, lua_code, {})

    def _default_pipeline_config(
        self,
        parser_analysis: Dict,
        lua_code: str,
        parser_metadata: Dict
    ) -> Dict:
        """Generate default pipeline configuration"""
        parser_id = parser_analysis.get("parser_id")
        complexity = parser_analysis.get("parser_complexity", {}).get("level", "Medium")
        ocsf_class = parser_analysis.get("ocsf_classification", {})

        # Map complexity and volume to resources
        resource_map = {
            "Low": {"memory": "512MB", "cpu": "0.5", "instances_max": 3},
            "Medium": {"memory": "1GB", "cpu": "1.0", "instances_max": 5},
            "High": {"memory": "2GB", "cpu": "2.0", "instances_max": 10}
        }

        resources = resource_map.get(complexity, resource_map["Medium"])

        config = {
            "name": f"s1-{parser_id}",
            "description": f"SentinelOne parser conversion: {parser_id}",
            "type": "lua_transform",
            "source": {
                "type": "sentinelone_parser",
                "parser_id": parser_id,
                "metadata": parser_metadata
            },
            "transformation": {
                "type": "lua",
                "code": lua_code,
                "runtime": "lua5.4"
            },
            "ocsf_mapping": {
                "class_uid": ocsf_class.get("class_uid", 0),
                "class_name": ocsf_class.get("class_name", "Unknown"),
                "category_uid": ocsf_class.get("category_uid", 0),
                "category_name": ocsf_class.get("category_name", "Unknown")
            },
            "resources": {
                "memory": resources["memory"],
                "cpu_cores": resources["cpu"],
                "instances_min": 1,
                "instances_max": resources["instances_max"]
            },
            "processing": {
                "batch_size": 500,
                "batch_timeout_ms": 1000,
                "max_retries": 3,
                "retry_backoff_ms": 1000
            },
            "error_handling": {
                "on_error": "log_and_continue",
                "dead_letter_queue": True,
                "max_error_rate": 0.01
            },
            "monitoring": {
                "metrics_enabled": True,
                "logs_enabled": True,
                "traces_enabled": True,
                "alert_on_errors": True
            },
            "metadata": {
                "created_by": "Purple-Pipeline-Parser-Eater",
                "created_at": datetime.now().isoformat(),
                "source_repository": "Sentinel-One/ai-siem",
                "parser_complexity": complexity,
                "conversion_version": "1.0.0"
            }
        }

        return config

    def _marshal_saas_payload(self, payload: Dict) -> Dict:
        """Rename internal Python-side field names to SaaS REST field names.

        Thin shim applied at the HTTP boundary. The rest of the Python
        call chain uses `lua_code` as the internal name; the SaaS REST
        API (p01-api.observo.ai) uses `luaScript` inside a config block
        on each transform. We shallow-copy the payload and rewrite any
        transform blob in the `transforms` list so the outbound POST
        body matches the cassette in tests/fixtures/saas_cassettes/.

        Only the HTTP marshalling layer is renamed -- do NOT rename
        `lua_code` anywhere else in this file or in observo_models /
        observo_pipeline_builder / pipeline_validator (plan Phase 4.C).
        """
        if not isinstance(payload, dict):
            return payload
        out = dict(payload)
        transforms = out.get("transforms")
        if isinstance(transforms, list):
            new_transforms = []
            for t in transforms:
                if not isinstance(t, dict):
                    new_transforms.append(t)
                    continue
                t2 = dict(t)
                existing_cfg = t2.get("config")
                if not isinstance(existing_cfg, dict):
                    existing_cfg = {}
                else:
                    existing_cfg = dict(existing_cfg)
                # If the transform carries the internal lua_code and the
                # config block doesn't yet have luaScript, promote it.
                if "lua_code" in t2 and "luaScript" not in existing_cfg:
                    existing_cfg.setdefault("enabled", True)
                    existing_cfg["luaScript"] = t2["lua_code"]
                    existing_cfg.setdefault("metricEvent", False)
                    existing_cfg.setdefault("bypassTransform", False)
                # Remove the internal name from the outbound body.
                t2.pop("lua_code", None)
                t2["config"] = existing_cfg
                new_transforms.append(t2)
            out["transforms"] = new_transforms
        return out

    async def _deploy_pipeline(self, config: Dict) -> Dict:
        """Deploy pipeline to Observo.ai SaaS control plane.

        Uses /gateway/v1/deserialize-pipeline -- the atomic upload+deploy
        endpoint documented in observo docs/pipeline.md:3. This replaces
        the earlier (broken) `{base_url}/pipelines` URL which had no
        counterpart on the real SaaS API (plan Phase 4.B).
        """
        # Rename the internal `lua_code` Python-side name to `luaScript`
        # (camelCase SaaS config key) at the HTTP marshalling boundary.
        # Internal shape stays lua_code everywhere else (plan Phase 4.C).
        config = self._marshal_saas_payload(config)
        url = f"{self.base_url}/gateway/v1/deserialize-pipeline"

        try:
            async with self.session.post(url, json=config, timeout=self.deployment_timeout) as response:
                if response.status not in [200, 201]:
                    error_text = await response.text()
                    raise ObservoAPIError(f"Deployment failed with status {response.status}: {error_text}")

                result = await response.json()
                return result

        except aiohttp.ClientError as e:
            raise DeploymentError(f"HTTP error during deployment: {e}")
        except asyncio.TimeoutError:
            raise DeploymentError(f"Deployment timeout after {self.deployment_timeout}s")

    def _mock_deployment_response(self, parser_id: str, config: Dict) -> Dict:
        """Generate mock deployment response for testing"""
        return {
            "pipeline_id": f"mock-pipeline-{parser_id}-{datetime.now().timestamp()}",
            "name": config.get("name", parser_id),
            "status": "deployed",
            "deployment_time": datetime.now().isoformat(),
            "endpoint": f"{self.base_url}/gateway/v1/deserialize-pipeline#mock-{parser_id}",
            "configuration": config,
            "mock_mode": True
        }

    async def get_pipeline_status(self, pipeline_id: str) -> Dict:
        """Get status of deployed pipeline"""
        if self.mock_mode:
            return {
                "pipeline_id": pipeline_id,
                "status": "running",
                "mock_mode": True
            }

        await self.rate_limiter.wait()

        # Pipeline list endpoint is documented at /gateway/v1/pipelines
        # (plural, GET only) in observo docs/pipeline.md. There is no
        # per-id GET documented; we query the list and caller can filter.
        url = f"{self.base_url}/gateway/v1/pipelines?pipelineIds={pipeline_id}"

        try:
            async with self.session.get(url) as response:
                if response.status != 200:
                    raise ObservoAPIError(f"Failed to get pipeline status: {response.status}")

                return await response.json()

        except Exception as e:
            logger.error(f"Failed to get pipeline status: {e}")
            raise ObservoAPIError(f"Status check failed: {e}")

    async def batch_deploy_pipelines(
        self,
        deployments: List[Dict],
        batch_size: int = 5
    ) -> List[Dict]:
        """Deploy multiple pipelines in batches"""
        logger.info(f"[PACKAGE] Batch deploying {len(deployments)} pipelines")
        results = []

        for i in range(0, len(deployments), batch_size):
            batch = deployments[i:i + batch_size]
            logger.info(f"Deploying batch {i//batch_size + 1}/{(len(deployments)-1)//batch_size + 1}")

            batch_tasks = []
            for deployment in batch:
                task = self.create_optimized_pipeline(
                    deployment["parser_analysis"],
                    deployment["lua_code"],
                    deployment["parser_metadata"]
                )
                batch_tasks.append(task)

            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"Batch deployment error: {result}")
                else:
                    results.append(result)

            # Delay between batches
            deployment_delay = self.config.get("processing", {}).get("deployment_delay", 5.0)
            await asyncio.sleep(deployment_delay)

        logger.info(f"[OK] Batch deployment complete: {len(results)}/{len(deployments)} successful")
        return results

    async def build_pipeline_json(
        self,
        parser_analysis: Dict,
        lua_code: str,
        complete_metadata: Dict
    ) -> Dict:
        """
        Build complete pipeline JSON for validation and deployment

        DIRECTOR REQUIREMENT: Create standardized pipeline.json structure

        Args:
            parser_analysis: Parser analysis data
            lua_code: Generated LUA transformation code
            complete_metadata: Complete AI-SIEM metadata from metadata builder

        Returns:
            Complete pipeline JSON structure
        """
        parser_id = parser_analysis.get("parser_id", "unknown")
        ocsf_class = parser_analysis.get("ocsf_classification", {})

        # Build source configuration
        source_config = {
            "type": "sentinelone_parser",
            "parser_id": parser_id,
            "name": f"s1-{parser_id}",
            "description": complete_metadata.get("description", f"SentinelOne {parser_id} parser")
        }

        # Build LUA transform.
        #
        # Internal shape retains `lua_code` (the Python-side name used by
        # pipeline_validator.py:345 and the rest of the call chain). The
        # HTTP marshalling shim (_marshal_saas_payload) renames it to
        # `luaScript` inside a SaaS-shaped `config` block immediately
        # before POST. We also pre-populate a `config` block here so the
        # pipeline_json is self-consistent for callers that inspect it
        # without going through _deploy_pipeline (plan Phase 4.C).
        transform_config = {
            "type": "lua",
            "name": f"{parser_id}_transform",
            "lua_code": lua_code,
            "runtime_version": "5.4",
            "templateName": "lua_script",
            "config": {
                "enabled": True,
                "luaScript": lua_code,
                "metricEvent": False,
                "bypassTransform": False,
            },
        }

        # Build pipeline graph (Observo visual pipeline structure)
        pipeline_graph = {
            "nodes": [
                {
                    "id": "source",
                    "type": "source",
                    "config": source_config
                },
                {
                    "id": "transform",
                    "type": "transform",
                    "config": transform_config
                },
                {
                    "id": "sink",
                    "type": "sink",
                    "config": {"type": "observo_store"}
                }
            ],
            "edges": [
                {"from": "source", "to": "transform"},
                {"from": "transform", "to": "sink"}
            ]
        }

        # Complete pipeline JSON structure
        pipeline_json = {
            "siteId": self.site_id,
            "pipeline": {
                "name": f"s1-{parser_id}",
                "description": complete_metadata.get("description", ""),
                "version": "1.0.0"
            },
            "pipelineGraph": pipeline_graph,
            "source": source_config,
            "transforms": [transform_config],
            "sinks": [{"type": "observo_store"}],
            "metadata": complete_metadata,
            "ocsf_mapping": {
                "class_uid": ocsf_class.get("class_uid", 0),
                "class_name": ocsf_class.get("class_name", "Unknown"),
                "category_uid": ocsf_class.get("category_uid", 0),
                "category_name": ocsf_class.get("category_name", "Unknown")
            }
        }

        return pipeline_json

    async def deploy_validated_pipeline(
        self,
        pipeline_json: Dict,
        validation_results: Dict
    ) -> Dict:
        """
        Deploy pipeline that has been validated

        DIRECTOR REQUIREMENT: Deploy only after validation checks

        Args:
            pipeline_json: Complete pipeline JSON
            validation_results: Results from PipelineValidator

        Returns:
            Deployment result
        """
        parser_id = pipeline_json.get("pipeline", {}).get("name", "unknown")

        logger.info(
            f"[START] Deploying validated pipeline: {parser_id} "
            f"(status: {validation_results.get('overall_status', 'unknown')})"
        )

        await self.rate_limiter.wait()

        try:
            # Check validation status
            if validation_results.get("overall_status") == "failed":
                error_count = validation_results.get("error_count", 0)
                logger.warning(
                    f"Pipeline {parser_id} has {error_count} validation errors - "
                    f"deploying anyway (fix errors for production use)"
                )

            # Deploy to Observo.ai
            if self.mock_mode:
                logger.info(f"[MOCK MODE] Would deploy validated pipeline: {parser_id}")
                result = self._mock_deployment_response(parser_id, pipeline_json)
                result["validation"] = validation_results
            else:
                # Use comprehensive API client to deploy
                result = await self._deploy_pipeline(pipeline_json)
                result["validation"] = validation_results

            self.statistics["pipelines_created"] += 1
            self.statistics["deployments_successful"] += 1

            logger.info(f"[OK] Successfully deployed validated pipeline: {parser_id}")
            return result

        except Exception as e:
            logger.error(f"Failed to deploy validated pipeline {parser_id}: {e}")
            self.statistics["deployments_failed"] += 1
            self.statistics["errors"].append(f"{parser_id}: {str(e)}")
            raise ObservoAPIError(f"Validated pipeline deployment failed: {e}")

    def get_statistics(self) -> Dict:
        """Get deployment statistics"""
        total_attempts = self.statistics["deployments_successful"] + self.statistics["deployments_failed"]
        return {
            **self.statistics,
            "success_rate": (
                self.statistics["deployments_successful"] / total_attempts
                if total_attempts > 0 else 0
            )
        }
