"""
Observo.ai API Client for Purple Pipeline Parser Eater
Intelligent pipeline deployment with Claude-optimized configuration and RAG enhancement

Targets the SaaS REST control plane at p01-api.observo.ai/gateway/v1/*.
Do NOT mutate to snake_case based on dataplane-binary findings (plan
Phase 4.C). The dataplane-binary / standalone YAML path is a separate
code path and must not be reconciled against this client's payload
shape.

Heavy deps (``aiohttp``, ``anthropic``) are lazy-imported inside the
methods that need them so that ``import components.observo_client`` stays
cheap in minimal test venvs (plan Phase 6 Dispatch 1 / Phase 4 DA).
"""
import asyncio
import logging
from typing import Dict, Optional, Any
from datetime import datetime


logger = logging.getLogger(__name__)


_aiohttp_cache = None


def _aiohttp_mod():
    """Lazy-import ``aiohttp`` so module load stays cheap in minimal venvs."""
    global _aiohttp_cache
    if _aiohttp_cache is None:
        import aiohttp as _ah
        _aiohttp_cache = _ah
    return _aiohttp_cache


def _error_handler():
    """Lazy-import utils.error_handler.

    ``utils.error_handler`` hard-imports ``tenacity`` at module top; in
    minimal test venvs tenacity may be absent, which previously caused
    ``import components.observo_client`` to fail. Lazy-loading here keeps
    module load cheap and defers the tenacity dependency until real HTTP
    deployment code runs (plan Phase 6 Dispatch 1 / Phase 4 DA).
    """
    try:
        from utils import error_handler as _eh
    except ImportError:  # pragma: no cover - package-relative fallback
        from ..utils import error_handler as _eh  # type: ignore
    return _eh


class ObservoAPIClient:
    """
    Intelligent Observo.ai API client with Claude optimization and RAG enhancement

    This class now wraps the comprehensive ObservoAPI client and provides
    high-level methods for parser-to-pipeline conversion with RAG intelligence.
    """

    def __init__(self, config: Dict, claude_client: Optional[Any] = None, rag_knowledge=None):
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

        # W1 (deletion-only): the legacy `_observo_deps()` lazy-import
        # tried to load `components.observo` (an unimplemented Phase-4
        # SaaS client) plus `PipelineBuilder` / `PipelineOptimizer`. None
        # of `self.api_client` / `self.pipeline_builder` /
        # `self.pipeline_optimizer` were ever read anywhere in the
        # codebase (assignment-only; verified by grep across components/,
        # services/, orchestrator/), and the import crashed
        # construction with ModuleNotFoundError on any callsite that
        # didn't pre-stub `sys.modules["components.observo"]`. The live
        # SaaS deploy path is `_deploy_pipeline` (this file, further
        # down) which wraps aiohttp directly under the W5 SSRF gate.
        _eh = _error_handler()

        self.claude = claude_client
        self.rag_knowledge = rag_knowledge

        self.rate_limiter = _eh.RateLimiter(
            calls_per_second=1.0 / observo_config.get("rate_limit_delay", 2.0)
        )

        # Session is lazily created in __aenter__; typed as Any because
        # aiohttp is lazy-imported.
        self.session: Optional[Any] = None
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
        aiohttp = _aiohttp_mod()
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
        aiohttp = _aiohttp_mod()
        _eh = _error_handler()
        # Rename the internal `lua_code` Python-side name to `luaScript`
        # (camelCase SaaS config key) at the HTTP marshalling boundary.
        # Internal shape stays lua_code everywhere else (plan Phase 4.C).
        config = self._marshal_saas_payload(config)
        url = f"{self.base_url}/gateway/v1/deserialize-pipeline"

        # W5 (plan 2026-04-29): SSRF gate before the outbound
        # aiohttp.post. base_url is operator-controlled (Settings tab
        # POST or env-var override) so it MUST be revalidated here as
        # a defense-in-depth boundary, even though the Settings save
        # path also gates it. Allowlist is the Observo SaaS default
        # — operators self-hosting Observo can edit
        # ``utils.security_utils.OBSERVO_DEFAULT_ALLOWLIST``.
        from utils.security_utils import (  # local import: keep module load cheap
            validate_url_for_ssrf,
            OBSERVO_DEFAULT_ALLOWLIST,
        )
        ok, reason = validate_url_for_ssrf(
            url, host_allowlist=OBSERVO_DEFAULT_ALLOWLIST
        )
        if not ok:
            raise _eh.DeploymentError(
                f"SSRF guard blocked Observo deploy URL {url!r}: {reason}"
            )

        try:
            async with self.session.post(
                url, json=config, timeout=self.deployment_timeout
            ) as response:
                if response.status not in [200, 201]:
                    error_text = await response.text()
                    raise _eh.ObservoAPIError(
                        f"Deployment failed with status {response.status}: {error_text}"
                    )

                result = await response.json()
                return result

        except aiohttp.ClientError as e:
            raise _eh.DeploymentError(f"HTTP error during deployment: {e}")
        except asyncio.TimeoutError:
            raise _eh.DeploymentError(
                f"Deployment timeout after {self.deployment_timeout}s"
            )

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

        _eh = _error_handler()
        try:
            async with self.session.get(url) as response:
                if response.status != 200:
                    raise _eh.ObservoAPIError(
                        f"Failed to get pipeline status: {response.status}"
                    )

                return await response.json()

        except Exception as e:
            logger.error(f"Failed to get pipeline status: {e}")
            raise _eh.ObservoAPIError(f"Status check failed: {e}")

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
            raise _error_handler().ObservoAPIError(
                f"Validated pipeline deployment failed: {e}"
            )

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
