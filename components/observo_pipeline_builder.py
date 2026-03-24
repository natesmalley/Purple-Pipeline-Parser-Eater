"""
Observo.ai Pipeline Builder
Intelligent pipeline construction from parser analysis and LUA code
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import json

try:
    from .observo_models import (
        Pipeline, PipelineGraph, Source, Sink, Transform,
        PipelineType, NodeStatus, NodeOrigin, SourceType, SinkType,
        LogFormat, create_lua_transform, create_simple_pipeline_graph,
        NodeIds
    )
except ImportError:
    from observo_models import (
        Pipeline, PipelineGraph, Source, Sink, Transform,
        PipelineType, NodeStatus, NodeOrigin, SourceType, SinkType,
        LogFormat, create_lua_transform, create_simple_pipeline_graph,
        NodeIds
    )


logger = logging.getLogger(__name__)


class PipelineBuilder:
    """
    Intelligent pipeline builder for Observo.ai

    Constructs complete pipeline configurations from:
    - Parser analysis
    - LUA transformation code
    - OCSF mappings
    - Performance characteristics
    """

    def __init__(self, site_id: int):
        """
        Initialize pipeline builder

        Args:
            site_id: Observo site ID for pipeline deployment
        """
        self.site_id = site_id

    def build_pipeline_from_parser(
        self,
        parser_name: str,
        parser_analysis: Dict[str, Any],
        lua_code: str,
        parser_metadata: Dict[str, Any],
        destination_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Build complete pipeline from parser analysis

        Args:
            parser_name: Parser name
            parser_analysis: Claude's parser analysis
            lua_code: Generated LUA transformation code
            parser_metadata: SentinelOne parser metadata
            destination_config: Destination configuration (optional)

        Returns:
            Complete pipeline definition ready for deployment
        """
        logger.info(f"Building pipeline for parser: {parser_name}")

        # Extract analysis components
        complexity = parser_analysis.get("parser_complexity", {}).get("level", "Medium")
        ocsf_class = parser_analysis.get("ocsf_classification", {})
        performance = parser_analysis.get("performance_characteristics", {})

        # 1. Create Pipeline
        pipeline = self._create_pipeline(parser_name, parser_analysis, complexity)

        # 2. Create Source
        source = self._create_source(parser_name, parser_metadata, parser_analysis)

        # 3. Create LUA Transform
        lua_transform = self._create_lua_transform(parser_name, lua_code, parser_analysis)

        # 4. Create Destination(s)
        destinations = self._create_destinations(parser_name, destination_config)

        # 5. Create Pipeline Graph (topology)
        # Note: We don't have IDs yet, so we'll use placeholders
        # The actual graph will be created after components are added to Observo
        pipeline_graph = PipelineGraph(
            version=1,
            edges={},  # Will be populated after component creation
            created=datetime.now().isoformat(),
            createdBy="Purple-Pipeline-Parser-Eater"
        )

        # 6. Assemble complete definition
        pipeline_definition = {
            "siteId": self.site_id,
            "pipeline": pipeline,
            "pipelineGraph": pipeline_graph,
            "source": source,
            "transforms": [lua_transform],
            "destinations": destinations,
            "archivalDestination": None,
            "deployPipeline": False,  # Don't deploy immediately
            "metadata": {
                "parser_name": parser_name,
                "complexity": complexity,
                "ocsf_classification": ocsf_class,
                "performance_characteristics": performance,
                "created_by": "Purple-Pipeline-Parser-Eater",
                "created_at": datetime.now().isoformat()
            }
        }

        logger.info(f"Pipeline definition created for {parser_name}")
        return pipeline_definition

    def _create_pipeline(
        self,
        parser_name: str,
        parser_analysis: Dict[str, Any],
        complexity: str
    ) -> Pipeline:
        """Create pipeline configuration"""
        description = self._generate_pipeline_description(parser_name, parser_analysis)

        return Pipeline(
            siteId=self.site_id,
            name=f"s1-{parser_name}",
            description=description,
            status="DEFAULT",
            pipelineType=PipelineType.USER.value,
            pendingAction="NOP"
        )

    def _create_source(
        self,
        parser_name: str,
        parser_metadata: Dict[str, Any],
        parser_analysis: Dict[str, Any]
    ) -> Source:
        """Create source configuration"""
        # Determine log format from parser analysis
        log_format = self._determine_log_format(parser_metadata, parser_analysis)

        # Build source configuration
        source_config = {
            "description": f"SentinelOne parser: {parser_name}",
            "parser_type": parser_metadata.get("type", ""),
            "parser_version": parser_metadata.get("version", "1.0"),
            "original_parser_path": parser_metadata.get("path", ""),
            "sentinelone_metadata": parser_metadata
        }

        return Source(
            siteId=self.site_id,
            templateId=0,  # Will be set based on source type selection
            templateVersion=1,
            templateName="DEMO_LOGS",  # Default to demo logs for testing
            name=f"source-{parser_name}",
            description=f"Source for SentinelOne parser: {parser_name}",
            config=source_config,
            status=NodeStatus.ACTIVE.value,
            type=SourceType.DEMO_LOGS.value,  # Default to demo logs
            origin=NodeOrigin.USER.value,
            logFormat=log_format,
            userVisible=True
        )

    def _create_lua_transform(
        self,
        parser_name: str,
        lua_code: str,
        parser_analysis: Dict[str, Any]
    ) -> Transform:
        """Create LUA script transform"""
        description = self._generate_transform_description(parser_name, parser_analysis)

        # Build LUA configuration
        lua_config = {
            "enabled": True,
            "luaScript": lua_code,
            "metricEvent": False,
            "bypassTransform": False,
            "filterConditions": None
        }

        return Transform(
            siteId=self.site_id,
            templateId=0,  # Will be set by Observo
            templateVersion=1,
            name=f"transform-lua-{parser_name}",
            description=description,
            config=lua_config,
            status=NodeStatus.ACTIVE.value,
            origin=NodeOrigin.USER.value,
            templateName="lua_script",
            processorType="DATA_PROCESSOR",
            userVisible=True
        )

    def _create_destinations(
        self,
        parser_name: str,
        destination_config: Optional[Dict[str, Any]] = None
    ) -> List[Sink]:
        """Create destination sink(s)"""
        if not destination_config:
            # Default to blackhole sink for testing
            return [self._create_blackhole_sink(parser_name)]

        # Parse destination config and create appropriate sinks
        destinations = []

        dest_type = destination_config.get("type", "BLACKHOLE")
        if dest_type == "BLACKHOLE":
            destinations.append(self._create_blackhole_sink(parser_name))
        elif dest_type == "ELASTICSEARCH":
            destinations.append(self._create_elasticsearch_sink(parser_name, destination_config))
        elif dest_type == "SPLUNK_HEC_LOGS":
            destinations.append(self._create_splunk_sink(parser_name, destination_config))
        elif dest_type == "AWS_S3":
            destinations.append(self._create_s3_sink(parser_name, destination_config))
        else:
            logger.warning(f"Unknown destination type: {dest_type}, defaulting to blackhole")
            destinations.append(self._create_blackhole_sink(parser_name))

        return destinations

    def _create_blackhole_sink(self, parser_name: str) -> Sink:
        """Create blackhole sink (for testing)"""
        return Sink(
            siteId=self.site_id,
            templateId=0,
            templateVersion=1,
            templateName="BLACKHOLE",
            name=f"sink-blackhole-{parser_name}",
            description=f"Test sink for {parser_name} (discards events)",
            config={},
            status=NodeStatus.ACTIVE.value,
            type=SinkType.BLACKHOLE.value,
            origin=NodeOrigin.USER.value,
            usageType="USER",
            userVisible=True
        )

    def _create_elasticsearch_sink(
        self,
        parser_name: str,
        config: Dict[str, Any]
    ) -> Sink:
        """Create Elasticsearch sink"""
        es_config = {
            "endpoints": config.get("endpoints", []),
            "index": config.get("index", f"sentinelone-{parser_name}"),
            "api_key": config.get("api_key", ""),
            "tls_enabled": config.get("tls_enabled", True),
            "compression": config.get("compression", "gzip")
        }

        return Sink(
            siteId=self.site_id,
            templateId=0,
            templateVersion=1,
            templateName="ELASTICSEARCH",
            name=f"sink-elasticsearch-{parser_name}",
            description=f"Elasticsearch sink for {parser_name}",
            config=es_config,
            status=NodeStatus.ACTIVE.value,
            type=SinkType.ELASTICSEARCH.value,
            origin=NodeOrigin.USER.value,
            usageType="USER",
            userVisible=True
        )

    def _create_splunk_sink(
        self,
        parser_name: str,
        config: Dict[str, Any]
    ) -> Sink:
        """Create Splunk HEC sink"""
        splunk_config = {
            "endpoint": config.get("endpoint", ""),
            "token": config.get("token", ""),
            "index": config.get("index", f"sentinelone_{parser_name}"),
            "source": config.get("source", "observo"),
            "sourcetype": config.get("sourcetype", f"sentinelone:{parser_name}"),
            "tls_enabled": config.get("tls_enabled", True)
        }

        return Sink(
            siteId=self.site_id,
            templateId=0,
            templateVersion=1,
            templateName="SPLUNK_HEC_LOGS",
            name=f"sink-splunk-{parser_name}",
            description=f"Splunk HEC sink for {parser_name}",
            config=splunk_config,
            status=NodeStatus.ACTIVE.value,
            type=SinkType.SPLUNK_HEC_LOGS.value,
            origin=NodeOrigin.USER.value,
            usageType="USER",
            userVisible=True
        )

    def _create_s3_sink(
        self,
        parser_name: str,
        config: Dict[str, Any]
    ) -> Sink:
        """Create AWS S3 sink"""
        s3_config = {
            "bucket": config.get("bucket", ""),
            "region": config.get("region", "us-east-1"),
            "prefix": config.get("prefix", f"sentinelone/{parser_name}/"),
            "compression": config.get("compression", "gzip"),
            "encoding": config.get("encoding", "json"),
            "credentials": config.get("credentials", {})
        }

        return Sink(
            siteId=self.site_id,
            templateId=0,
            templateVersion=1,
            templateName="AWS_S3",
            name=f"sink-s3-{parser_name}",
            description=f"AWS S3 sink for {parser_name}",
            config=s3_config,
            status=NodeStatus.ACTIVE.value,
            type=SinkType.AWS_S3.value,
            origin=NodeOrigin.USER.value,
            usageType="USER",
            userVisible=True
        )

    def create_pipeline_graph(
        self,
        source_id: int,
        transform_ids: List[int],
        sink_ids: List[int],
        pipeline_id: Optional[int] = None
    ) -> PipelineGraph:
        """
        Create pipeline graph after components are created

        Args:
            source_id: Created source ID
            transform_ids: Created transform IDs (in order)
            sink_ids: Created sink IDs
            pipeline_id: Pipeline ID (if available)

        Returns:
            PipelineGraph with proper node connections
        """
        edges = {}

        # Source connects to first transform (or sinks if no transforms)
        if transform_ids:
            edges[str(source_id)] = NodeIds(nodeIds=[transform_ids[0]])

            # Transforms connect to each other in sequence
            for i in range(len(transform_ids) - 1):
                edges[str(transform_ids[i])] = NodeIds(nodeIds=[transform_ids[i + 1]])

            # Last transform connects to all sinks
            edges[str(transform_ids[-1])] = NodeIds(nodeIds=sink_ids)
        else:
            # Source directly to sinks
            edges[str(source_id)] = NodeIds(nodeIds=sink_ids)

        return PipelineGraph(
            version=1,
            pipelineId=pipeline_id,
            edges=edges,
            created=datetime.now().isoformat(),
            createdBy="Purple-Pipeline-Parser-Eater"
        )

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _determine_log_format(
        self,
        parser_metadata: Dict[str, Any],
        parser_analysis: Dict[str, Any]
    ) -> str:
        """Determine log format from parser metadata and analysis"""
        # Check parser file name and type
        parser_path = parser_metadata.get("path", "").lower()

        if "cloudtrail" in parser_path:
            return LogFormat.CLOUDTRAIL.value
        elif "vpc" in parser_path or "flowlog" in parser_path:
            return LogFormat.AWS_VPC_FLOWLOGS.value
        elif "syslog" in parser_path:
            return LogFormat.SYSLOG.value
        elif "cef" in parser_path:
            return LogFormat.CEF.value
        elif "json" in parser_path or ".json" in parser_path:
            return LogFormat.JSON.value

        # Default to JSON for most parsers
        return LogFormat.JSON.value

    def _generate_pipeline_description(
        self,
        parser_name: str,
        parser_analysis: Dict[str, Any]
    ) -> str:
        """Generate comprehensive pipeline description"""
        ocsf_class = parser_analysis.get("ocsf_classification", {}).get("class_name", "Unknown")
        complexity = parser_analysis.get("parser_complexity", {}).get("level", "Medium")

        return (
            f"SentinelOne parser conversion: {parser_name} | "
            f"OCSF Class: {ocsf_class} | "
            f"Complexity: {complexity} | "
            f"Auto-generated by Purple Pipeline Parser Eater"
        )

    def _generate_transform_description(
        self,
        parser_name: str,
        parser_analysis: Dict[str, Any]
    ) -> str:
        """Generate transform description"""
        fields_mapped = len(parser_analysis.get("field_mappings", []))

        return (
            f"LUA transformation for {parser_name} | "
            f"Fields mapped: {fields_mapped} | "
            f"OCSF-compliant output"
        )


class PipelineOptimizer:
    """
    Pipeline optimization based on performance characteristics

    Optimizes:
    - Resource allocation
    - Batch sizes
    - Error handling
    - Scaling parameters
    """

    def __init__(self):
        self.optimization_rules = {
            "Low": {
                "batch_size": 100,
                "max_concurrent": 2,
                "memory_mb": 512,
                "cpu_cores": 0.5
            },
            "Medium": {
                "batch_size": 500,
                "max_concurrent": 5,
                "memory_mb": 1024,
                "cpu_cores": 1.0
            },
            "High": {
                "batch_size": 1000,
                "max_concurrent": 10,
                "memory_mb": 2048,
                "cpu_cores": 2.0
            }
        }

    def optimize_pipeline_config(
        self,
        complexity: str,
        expected_volume: str,
        parser_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate optimized pipeline configuration

        Args:
            complexity: Parser complexity (Low, Medium, High)
            expected_volume: Expected data volume
            parser_analysis: Parser analysis data

        Returns:
            Optimized configuration parameters
        """
        base_config = self.optimization_rules.get(complexity, self.optimization_rules["Medium"])

        # Adjust for expected volume
        volume_multiplier = {
            "Low": 0.5,
            "Medium": 1.0,
            "High": 2.0,
            "Very High": 4.0
        }.get(expected_volume, 1.0)

        optimized_config = {
            "batch_size": int(base_config["batch_size"] * volume_multiplier),
            "max_concurrent": int(base_config["max_concurrent"] * volume_multiplier),
            "memory_mb": int(base_config["memory_mb"] * volume_multiplier),
            "cpu_cores": base_config["cpu_cores"] * volume_multiplier,
            "error_handling": {
                "max_retries": 3,
                "retry_backoff_ms": 1000,
                "dead_letter_queue": True,
                "max_error_rate": 0.01
            },
            "monitoring": {
                "metrics_enabled": True,
                "logs_enabled": True,
                "traces_enabled": True,
                "alert_on_errors": True
            }
        }

        return optimized_config
