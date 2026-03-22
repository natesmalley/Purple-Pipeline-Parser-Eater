"""
Observo.ai API Data Models
Complete type-safe models for Observo.ai API integration
"""
from typing import Dict, List, Optional, Any, Union
from enum import Enum
from dataclasses import dataclass, field, asdict
from datetime import datetime
import json


# ============================================================================
# Enumerations
# ============================================================================

class PipelineStatus(str, Enum):
    """Pipeline deployment status"""
    DEFAULT = "DEFAULT"
    TO_DEPLOY = "TO_DEPLOY"
    DEPLOYING = "DEPLOYING"
    DEPLOYED = "DEPLOYED"
    ROLLED_BACK = "ROLLED_BACK"
    FAILED = "FAILED"
    DELETED = "DELETED"
    DELETING = "DELETING"
    TO_DELETE = "TO_DELETE"
    PAUSED = "PAUSED"
    BYPASSED = "BYPASSED"


class PipelineType(str, Enum):
    """Pipeline type classification"""
    UNSPECIFIED = "PIPELINE_TYPE_UNSPECIFIED"
    PATTERN = "PIPELINE_TYPE_PATTERN"
    ARCHIVAL = "PIPELINE_TYPE_ARCHIVAL"
    USER = "PIPELINE_TYPE_USER"  # Enum value, not a credential
    SSA = "PIPELINE_TYPE_SSA"


class PipelineAction(str, Enum):
    """Pending pipeline actions"""
    NOP = "NOP"
    DEPLOY = "DEPLOY"
    DELETE = "DELETE"
    PAUSE = "PAUSE"
    BYPASS = "BYPASS"
    CANCEL = "CANCEL"


class NodeStatus(str, Enum):
    """Node (source/sink/transform) status"""
    DEFAULT = "NS_DEFAULT"
    ACTIVE = "NS_ACTIVE"
    DELETED = "NS_DELETED"
    INACTIVE = "NS_INACTIVE"


class NodeOrigin(str, Enum):
    """Origin of node creation"""
    DEFAULT = "NODE_ORIGIN_DEFAULT"
    USER = "NODE_ORIGIN_USER"  # Enum value, not a credential
    PATTERN = "NODE_ORIGIN_PATTERN"
    ARCHIVAL = "NODE_ORIGIN_ARCHIVAL"
    PREPROCESSOR = "NODE_ORIGIN_PREPROCESSOR"
    POSTPROCESSOR = "NODE_ORIGIN_POSTPROCESSOR"
    SSA = "NODE_ORIGIN_SSA"
    ANALYTICS_TAP = "NODE_ANALYTICS_TAP"


class SourceType(str, Enum):
    """Source connector types"""
    DEFAULT = "DEFAULT_TYPE"
    DATADOG_AGENT = "DATADOG_AGENT"
    DEMO_LOGS = "DEMO_LOGS"
    AWS_S3 = "AWS_S3"
    FLUENT = "FLUENT"
    OPENTELEMETRY = "OPENTELEMETRY"
    SYSLOG = "SYSLOG"
    KAFKA = "KAFKA"
    AWS_KINESIS_FIREHOSE = "AWS_KINESIS_FIREHOSE"
    LOGSTASH = "LOGSTASH"
    HTTP = "HTTP"
    GCP_PUBSUB = "GCP_PUBSUB"
    SOCKET = "SOCKET"
    STDIN = "STDIN"
    PROMETHEUS_REMOTE_WRITE = "PROMETHEUS_REMOTE_WRITE"
    VECTOR = "VECTOR"
    SPLUNK_HEC = "SPLUNK_HEC"
    SPLUNK_S2S = "SPLUNK_S2S"
    GCP_GCS = "GCP_GCS"


class SinkType(str, Enum):
    """Sink/destination connector types"""
    DEFAULT = "DEFAULT_TYPE"
    AWS_S3 = "AWS_S3"
    FILE = "FILE"
    HTTP = "HTTP"
    BLACKHOLE = "BLACKHOLE"
    ELASTICSEARCH = "ELASTICSEARCH"
    KAFKA = "KAFKA"
    SOCKET = "SOCKET"
    SPLUNK_HEC_LOGS = "SPLUNK_HEC_LOGS"
    LOKI = "LOKI"
    DATADOG_EVENTS = "DATADOG_EVENTS"
    DATADOG_LOGS = "DATADOG_LOGS"
    DATADOG_METRICS = "DATADOG_METRICS"
    DATADOG_TRACES = "DATADOG_TRACES"
    GCP_CLOUD_STORAGE = "GCP_CLOUD_STORAGE"
    NEW_RELIC = "NEW_RELIC"
    AZURE_MONITOR_LOGS = "AZURE_MONITOR_LOGS"
    AZURE_SENTINEL_LOGS = "AZURE_SENTINEL_LOGS"
    GCP_CHRONICLE_UNSTRUCTURED = "GCP_CHRONICLE_UNSTRUCTURED"
    AZURE_BLOB = "AZURE_BLOB"
    SPLUNK_HEC_METRICS = "SPLUNK_HEC_METRICS"
    PROMETHEUS_EXPORTER = "PROMETHEUS_EXPORTER"
    PROMETHEUS_REMOTE_WRITE = "PROMETHEUS_REMOTE_WRITE"


class LogFormat(str, Enum):
    """Log parsing formats"""
    UNSPECIFIED = "LOG_FORMAT_UNSPECIFIED"
    CLOUDTRAIL = "CLOUDTRAIL"
    JSON = "JSON"
    RAW = "RAW"
    AWS_VPC_FLOWLOGS = "AWS_VPC_FLOWLOGS"
    GROK = "GROK"
    SYSLOG = "SYSLOG"
    CEF = "CEF"
    KEY_VALUE = "KEY_VALUE"
    AWS_CLOUDWATCH_SUBSCRIPTION = "AWS_CLOUDWATCH_SUBSCRIPTION"


class TransformCategory(str, Enum):
    """Transform categorization"""
    DEFAULT = "DEFAULT"
    PARSER = "PARSER"
    SOURCE_CONFIG = "SOURCE_CONFIG"
    INTERNAL = "INTERNAL"
    PATTERN_EXTRACTOR = "PATTERN_EXTRACTOR"
    FUNCTION = "FUNCTION"
    SERIALIZER = "SERIALIZER"
    OPTIMIZER = "OPTIMIZER"
    DEPRECATED = "DEPRECATED"


class ProcessorType(str, Enum):
    """Processor execution type"""
    UNSPECIFIED = "PROCESSOR_TYPE_UNSPECIFIED"
    GENERIC_PREPROCESSOR = "GENERIC_PREPROCESSOR"
    CUSTOM_PREPROCESSOR = "CUSTOM_PREPROCESSOR"
    GENERIC_POSTPROCESSOR = "GENERIC_POSTPROCESSOR"
    CUSTOM_POSTPROCESSOR = "CUSTOM_POSTPROCESSOR"
    DATA_PROCESSOR = "DATA_PROCESSOR"


# ============================================================================
# Base Models
# ============================================================================

@dataclass
class ResponseStatus:
    """API response status"""
    code: str = "OK"  # OK, INVALID_PARAMS, SERVER_ERROR
    errorMessage: Optional[str] = None
    userMessageCode: str = "DEFAULT"


@dataclass
class Pagination:
    """Pagination parameters"""
    offset: int = 0
    limit: int = 100
    totalCount: int = 0
    ordering: Optional[Dict[str, Any]] = None


# ============================================================================
# Site Models
# ============================================================================

@dataclass
class Site:
    """Observo.ai site configuration"""
    id: Optional[int] = None
    name: str = ""
    description: str = ""
    orgId: str = ""
    status: str = "ACTIVE"
    vendor: str = "DEFAULT_TYPE"  # AWS, AZURE, GCP, ON_PREMISE
    created: Optional[str] = None
    updated: Optional[str] = None
    createdBy: Optional[str] = None
    updatedBy: Optional[str] = None


# ============================================================================
# Source Models
# ============================================================================

@dataclass
class SourceConfig:
    """Source-specific configuration"""
    id: Optional[int] = None
    sourceId: Optional[int] = None
    templateId: Optional[int] = None
    templateName: Optional[str] = None
    category: str = TransformCategory.DEFAULT.value
    config: Dict[str, Any] = field(default_factory=dict)
    position: int = 0
    templateVersion: int = 1


@dataclass
class Source:
    """Data source configuration"""
    id: Optional[int] = None
    siteId: int = 0
    templateId: int = 0
    templateVersion: int = 1
    templateName: str = ""
    name: str = ""
    description: str = ""
    config: Dict[str, Any] = field(default_factory=dict)
    status: str = NodeStatus.ACTIVE.value
    created: Optional[str] = None
    updated: Optional[str] = None
    createdBy: Optional[str] = None
    updatedBy: Optional[str] = None
    type: str = SourceType.DEFAULT.value
    origin: str = NodeOrigin.USER.value
    logFormat: str = LogFormat.JSON.value
    preprocessorConfig: Dict[str, Any] = field(default_factory=dict)
    port: Optional[int] = None
    pushBased: bool = False
    pushSourceAddress: Optional[str] = None
    k8sInternalSvcUrl: Optional[str] = None
    siteFilenames: List[str] = field(default_factory=list)
    sourceConfigs: List[SourceConfig] = field(default_factory=list)
    userVisible: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API calls"""
        data = asdict(self)
        # Remove None values
        return {k: v for k, v in data.items() if v is not None}


@dataclass
class SourceTemplate:
    """Source template definition"""
    id: Optional[int] = None
    type: str = SourceType.DEFAULT.value
    displayName: str = ""
    configFormat: Dict[str, Any] = field(default_factory=dict)
    version: int = 1


# ============================================================================
# Sink/Destination Models
# ============================================================================

@dataclass
class Sink:
    """Data sink/destination configuration"""
    id: Optional[int] = None
    siteId: int = 0
    templateId: int = 0
    templateVersion: int = 1
    templateName: str = ""
    name: str = ""
    description: str = ""
    config: Dict[str, Any] = field(default_factory=dict)
    status: str = NodeStatus.ACTIVE.value
    sourceId: Optional[int] = None
    created: Optional[str] = None
    updated: Optional[str] = None
    createdBy: Optional[str] = None
    updatedBy: Optional[str] = None
    type: str = SinkType.DEFAULT.value
    origin: str = NodeOrigin.USER.value
    usageType: str = "USER"  # USER, ARCHIVAL, PATTERN_EXTRACTOR, SSA
    siteFilenames: List[str] = field(default_factory=list)
    userVisible: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API calls"""
        data = asdict(self)
        return {k: v for k, v in data.items() if v is not None}


# ============================================================================
# Transform Models
# ============================================================================

@dataclass
class LuaTransformConfig:
    """Lua script transform configuration"""
    enabled: bool = True
    luaScript: str = ""
    metricEvent: bool = False
    bypassTransform: bool = False
    filterConditions: Optional[Dict[str, Any]] = None


@dataclass
class Transform:
    """Data transformation configuration"""
    id: Optional[int] = None
    siteId: int = 0
    templateId: int = 0
    templateVersion: int = 1
    name: str = ""
    description: str = ""
    pipelineId: Optional[int] = None
    config: Dict[str, Any] = field(default_factory=dict)
    status: str = NodeStatus.ACTIVE.value
    created: Optional[str] = None
    updated: Optional[str] = None
    createdBy: Optional[str] = None
    updatedBy: Optional[str] = None
    isTransformGroup: bool = False
    origin: str = NodeOrigin.USER.value
    templateName: str = ""
    processorType: str = ProcessorType.DATA_PROCESSOR.value
    siteFilenames: List[str] = field(default_factory=list)
    userVisible: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API calls"""
        data = asdict(self)
        return {k: v for k, v in data.items() if v is not None}


# ============================================================================
# Pipeline Models
# ============================================================================

@dataclass
class NodeIds:
    """Collection of node IDs"""
    nodeIds: List[int] = field(default_factory=list)


@dataclass
class PipelineGraph:
    """Pipeline graph structure"""
    version: int = 1
    pipelineId: Optional[int] = None
    edges: Dict[str, NodeIds] = field(default_factory=dict)  # node_id -> connected node_ids
    created: Optional[str] = None
    createdBy: Optional[str] = None
    metaInfo: Optional[Dict[str, Any]] = None


@dataclass
class Pipeline:
    """Complete pipeline configuration"""
    id: Optional[int] = None
    siteId: int = 0
    name: str = ""
    description: str = ""
    status: str = PipelineStatus.DEFAULT.value
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None
    deletedAt: Optional[str] = None
    createdBy: Optional[str] = None
    updatedBy: Optional[str] = None
    deployedGraphVersion: int = 0
    pendingGraphVersion: int = 0
    latestGraphVersion: int = 0
    sourceId: Optional[int] = None
    pipelineType: str = PipelineType.USER.value
    pendingAction: str = PipelineAction.NOP.value
    analytics: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API calls"""
        data = asdict(self)
        return {k: v for k, v in data.items() if v is not None}


@dataclass
class CompletePipelineDefinition:
    """Complete pipeline with all components"""
    pipeline: Pipeline
    pipelineGraph: PipelineGraph
    source: Source
    destinations: List[Sink]
    transforms: List[Transform]
    archivalDestination: Optional[Sink] = None
    deployPipeline: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API calls"""
        return {
            "pipeline": self.pipeline.to_dict(),
            "pipelineGraph": asdict(self.pipelineGraph),
            "source": self.source.to_dict(),
            "destinations": [dest.to_dict() for dest in self.destinations],
            "transforms": [t.to_dict() for t in self.transforms],
            "archivalDestination": self.archivalDestination.to_dict() if self.archivalDestination else None,
            "deployPipeline": self.deployPipeline
        }


# ============================================================================
# API Request/Response Models
# ============================================================================

@dataclass
class AddPipelineRequest:
    """Request to add new pipeline"""
    pipeline: Pipeline

    def to_dict(self) -> Dict[str, Any]:
        return {"pipeline": self.pipeline.to_dict()}


@dataclass
class AddPipelineResponse:
    """Response from adding pipeline"""
    status: ResponseStatus
    pipeline: Pipeline


@dataclass
class UpdatePipelineRequest:
    """Request to update pipeline"""
    pipeline: Pipeline
    lastUpdated: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pipeline": self.pipeline.to_dict(),
            "lastUpdated": self.lastUpdated
        }


@dataclass
class DeserializePipelineRequest:
    """Request to create complete pipeline from definition"""
    siteId: int
    pipeline: Pipeline
    pipelineGraph: PipelineGraph
    source: Source
    destinations: List[Sink]
    transforms: List[Transform]
    archivalDestination: Optional[Sink] = None
    deployPipeline: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "siteId": self.siteId,
            "pipeline": self.pipeline.to_dict(),
            "pipelineGraph": asdict(self.pipelineGraph),
            "source": self.source.to_dict(),
            "destinations": [dest.to_dict() for dest in self.destinations],
            "transforms": [t.to_dict() for t in self.transforms],
            "archivalDestination": self.archivalDestination.to_dict() if self.archivalDestination else None,
            "deployPipeline": self.deployPipeline
        }


@dataclass
class ListPipelinesResponse:
    """Response from listing pipelines"""
    pipelines: List[Pipeline]
    pagination: Pagination
    status: ResponseStatus


@dataclass
class AddSourceRequest:
    """Request to add new source"""
    source: Source

    def to_dict(self) -> Dict[str, Any]:
        return {"source": self.source.to_dict()}


@dataclass
class AddSinkRequest:
    """Request to add new sink"""
    sink: Sink

    def to_dict(self) -> Dict[str, Any]:
        return {"sink": self.sink.to_dict()}


@dataclass
class AddTransformRequest:
    """Request to add new transform"""
    transform: Transform

    def to_dict(self) -> Dict[str, Any]:
        return {"transform": self.transform.to_dict()}


# ============================================================================
# Helper Functions
# ============================================================================

def create_lua_transform(
    name: str,
    lua_script: str,
    description: str = "",
    site_id: int = 0
) -> Transform:
    """
    Create a Lua script transform configuration

    Args:
        name: Transform name
        lua_script: Lua script code
        description: Transform description
        site_id: Site ID

    Returns:
        Transform object configured for Lua script
    """
    lua_config = {
        "enabled": True,
        "luaScript": lua_script,
        "metricEvent": False,
        "bypassTransform": False
    }

    return Transform(
        siteId=site_id,
        name=name,
        description=description,
        config=lua_config,
        templateName="lua_script",
        processorType=ProcessorType.DATA_PROCESSOR.value,
        status=NodeStatus.ACTIVE.value,
        origin=NodeOrigin.USER.value
    )


def create_simple_pipeline_graph(
    source_id: int,
    transform_ids: List[int],
    sink_ids: List[int]
) -> PipelineGraph:
    """
    Create a simple linear pipeline graph

    Args:
        source_id: Source node ID
        transform_ids: List of transform node IDs (in order)
        sink_ids: List of sink node IDs

    Returns:
        PipelineGraph with linear flow: source -> transforms -> sinks
    """
    edges = {}

    # Source connects to first transform (or sinks if no transforms)
    if transform_ids:
        edges[str(source_id)] = NodeIds(nodeIds=[transform_ids[0]])

        # Transforms connect to each other
        for i in range(len(transform_ids) - 1):
            edges[str(transform_ids[i])] = NodeIds(nodeIds=[transform_ids[i + 1]])

        # Last transform connects to sinks
        edges[str(transform_ids[-1])] = NodeIds(nodeIds=sink_ids)
    else:
        # Source directly to sinks
        edges[str(source_id)] = NodeIds(nodeIds=sink_ids)

    return PipelineGraph(
        version=1,
        edges=edges,
        created=datetime.now().isoformat(),
        createdBy="Purple-Pipeline-Parser-Eater"
    )
