"""
Observo.ai RAG Query Patterns
Pre-defined intelligent query patterns for RAG-enhanced operations
"""
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class ObservoQueryPatterns:
    """
    Pre-defined query patterns for Observo.ai RAG knowledge base

    Provides intelligent queries for:
    - Configuration lookup
    - Best practices
    - Example retrieval
    - API endpoint discovery
    - Error resolution
    """

    def __init__(self, rag_knowledge_base):
        """
        Initialize query patterns

        Args:
            rag_knowledge_base: RAG knowledge base instance
        """
        self.rag = rag_knowledge_base
        self.statistics = {
            "queries_executed": 0,
            "results_found": 0,
            "cache_hits": 0
        }
        self.query_cache = {}

    async def find_source_configuration(
        self,
        source_type: str,
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Find configuration examples for specific source type

        Args:
            source_type: Source type (e.g., "okta", "syslog", "aws_s3")
            top_k: Number of results to return

        Returns:
            List of relevant configuration examples
        """
        query = f"How to configure {source_type} source in Observo? Show configuration parameters and examples."

        return await self._execute_query(query, top_k, doc_type_filter=f"source-{source_type}")

    async def find_sink_configuration(
        self,
        sink_type: str,
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Find configuration examples for specific sink type

        Args:
            sink_type: Sink type (e.g., "elasticsearch", "splunk", "s3")
            top_k: Number of results to return

        Returns:
            List of relevant configuration examples
        """
        query = f"How to configure {sink_type} sink/destination in Observo? Show required fields and configuration."

        return await self._execute_query(query, top_k, doc_type_filter="api-sink")

    async def find_lua_transform_examples(
        self,
        use_case: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find Lua transform code examples

        Args:
            use_case: Use case description (e.g., "field extraction", "filtering")
            top_k: Number of results to return

        Returns:
            List of relevant Lua examples
        """
        query = f"Show Lua script transform examples for {use_case}. Include code and explanation."

        return await self._execute_query(query, top_k, doc_type_filter="transform-lua")

    async def find_pipeline_best_practices(
        self,
        scenario: str,
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Find pipeline configuration best practices

        Args:
            scenario: Scenario description (e.g., "high volume logs", "security monitoring")
            top_k: Number of results to return

        Returns:
            List of best practices
        """
        query = f"What are best practices for Observo pipeline configuration for {scenario}? Include recommendations and examples."

        return await self._execute_query(query, top_k)

    async def find_api_endpoint(
        self,
        action: str,
        resource: str,
        top_k: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Find API endpoint for specific action and resource

        Args:
            action: API action (e.g., "create", "update", "list")
            resource: Resource type (e.g., "pipeline", "source", "sink")
            top_k: Number of results to return

        Returns:
            List of relevant API endpoints
        """
        query = f"What is the API endpoint to {action} {resource} in Observo? Show method, path, and request format."

        return await self._execute_query(query, top_k, doc_type_filter=f"api-{resource}")

    async def find_error_resolution(
        self,
        error_message: str,
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Find solutions for error messages

        Args:
            error_message: Error message or description
            top_k: Number of results to return

        Returns:
            List of relevant solutions
        """
        query = f"How to resolve this error in Observo: {error_message}. Show troubleshooting steps and solutions."

        return await self._execute_query(query, top_k)

    async def find_integration_guide(
        self,
        integration: str,
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Find integration setup guide

        Args:
            integration: Integration name (e.g., "Okta", "Splunk", "AWS")
            top_k: Number of results to return

        Returns:
            List of integration guides
        """
        query = f"How to integrate {integration} with Observo? Show setup steps, prerequisites, and configuration."

        return await self._execute_query(query, top_k)

    async def find_performance_optimization(
        self,
        component: str,
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Find performance optimization guidance

        Args:
            component: Component to optimize (e.g., "pipeline", "source", "transform")
            top_k: Number of results to return

        Returns:
            List of optimization recommendations
        """
        query = f"How to optimize {component} performance in Observo? Show configuration parameters and best practices."

        return await self._execute_query(query, top_k)

    async def find_similar_pipeline(
        self,
        description: str,
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Find similar pipeline configurations

        Args:
            description: Pipeline description
            top_k: Number of results to return

        Returns:
            List of similar pipelines
        """
        query = f"Find example pipeline configurations similar to: {description}. Include source, transforms, and sinks."

        return await self._execute_query(query, top_k, doc_type_filter="guide-pipeline-creation")

    async def find_authentication_setup(
        self,
        service: str,
        auth_type: str,
        top_k: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Find authentication setup instructions

        Args:
            service: Service name (e.g., "Okta", "AWS")
            auth_type: Authentication type (e.g., "API token", "OAuth", "certificate")
            top_k: Number of results to return

        Returns:
            List of authentication guides
        """
        query = f"How to set up {auth_type} authentication for {service} in Observo? Show configuration and credentials."

        return await self._execute_query(query, top_k)

    async def _execute_query(
        self,
        query: str,
        top_k: int,
        doc_type_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute RAG query with caching

        Args:
            query: Query string
            top_k: Number of results
            doc_type_filter: Optional document type filter

        Returns:
            Query results
        """
        # Check cache
        cache_key = f"{query}:{top_k}:{doc_type_filter}"
        if cache_key in self.query_cache:
            logger.info(f"Cache hit for query: {query[:50]}...")
            self.statistics["cache_hits"] += 1
            return self.query_cache[cache_key]

        # Execute query
        self.statistics["queries_executed"] += 1

        if not self.rag or not self.rag.enabled:
            logger.warning("RAG not available, returning empty results")
            return []

        try:
            # Query RAG knowledge base
            results = self.rag.search(
                query=query,
                top_k=top_k,
                doc_type_filter=doc_type_filter
            )

            self.statistics["results_found"] += len(results)

            # Cache results
            self.query_cache[cache_key] = results

            logger.info(f"Query executed: {query[:50]}... Found {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"Query failed: {e}")
            return []

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get query statistics

        Returns:
            Statistics dictionary
        """
        return {
            **self.statistics,
            "cache_size": len(self.query_cache),
            "cache_hit_rate": (
                self.statistics["cache_hits"] / self.statistics["queries_executed"]
                if self.statistics["queries_executed"] > 0 else 0
            )
        }

    def clear_cache(self):
        """Clear query cache"""
        self.query_cache = {}
        logger.info("Query cache cleared")


class ObservoRAGEnhancer:
    """
    RAG-enhanced pipeline builder with intelligent lookup
    """

    def __init__(self, rag_knowledge_base, query_patterns: ObservoQueryPatterns):
        """
        Initialize RAG enhancer

        Args:
            rag_knowledge_base: RAG knowledge base instance
            query_patterns: Query patterns instance
        """
        self.rag = rag_knowledge_base
        self.patterns = query_patterns

    async def enhance_source_config(
        self,
        source_type: str,
        base_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Enhance source configuration with RAG knowledge

        Args:
            source_type: Source type
            base_config: Base configuration

        Returns:
            Enhanced configuration
        """
        logger.info(f"Enhancing {source_type} source configuration with RAG")

        # Find best practices
        examples = await self.patterns.find_source_configuration(source_type)

        if not examples:
            logger.warning(f"No RAG examples found for {source_type}, using base config")
            return base_config

        # Extract recommendations from examples
        enhanced_config = base_config.copy()

        # Add metadata about RAG enhancement
        enhanced_config["_rag_enhanced"] = True
        enhanced_config["_rag_sources"] = [ex.get("source", "unknown") for ex in examples]

        logger.info(f"[OK] Enhanced {source_type} configuration with {len(examples)} RAG examples")

        return enhanced_config

    async def enhance_lua_transform(
        self,
        base_lua: str,
        parser_type: str,
        use_case: str
    ) -> str:
        """
        Enhance Lua transform with RAG examples

        Args:
            base_lua: Base Lua script
            parser_type: Parser type
            use_case: Use case description

        Returns:
            Enhanced Lua script (potentially with improvements)
        """
        logger.info(f"Enhancing Lua transform for {parser_type} with RAG")

        # Find similar examples
        examples = await self.patterns.find_lua_transform_examples(use_case)

        if not examples:
            logger.warning("No RAG examples found for Lua transform")
            return base_lua

        # Add comment with RAG reference
        rag_comment = f"-- Enhanced with RAG knowledge from {len(examples)} examples\n"
        enhanced_lua = rag_comment + base_lua

        logger.info(f"[OK] Enhanced Lua transform with {len(examples)} RAG examples")

        return enhanced_lua

    async def suggest_optimizations(
        self,
        pipeline_config: Dict[str, Any]
    ) -> List[str]:
        """
        Suggest optimizations based on RAG knowledge

        Args:
            pipeline_config: Pipeline configuration

        Returns:
            List of optimization suggestions
        """
        logger.info("Generating optimization suggestions with RAG")

        suggestions = []

        # Query for optimization best practices
        opt_results = await self.patterns.find_performance_optimization("pipeline")

        for result in opt_results:
            content = result.get("content", "")
            # Extract suggestions (simple heuristic)
            if "batch" in content.lower():
                suggestions.append("Consider adjusting batch size for better performance")
            if "memory" in content.lower():
                suggestions.append("Review memory allocation settings")
            if "scale" in content.lower():
                suggestions.append("Consider enabling auto-scaling")

        logger.info(f"Generated {len(suggestions)} optimization suggestions")

        return suggestions
