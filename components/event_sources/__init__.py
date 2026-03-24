"""Event sources for multi-source event ingestion."""

from .base_source import BaseEventSource
from .kafka_source import KafkaEventSource
from .scol_source import SCOLAPISource
from .s3_source import S3EventSource
from .azure_source import AzureEventHubsSource
from .gcp_source import GCPPubSubSource
from .syslog_hec_source import SyslogHECSource

__all__ = [
    "BaseEventSource",
    "KafkaEventSource",
    "SCOLAPISource",
    "S3EventSource",
    "AzureEventHubsSource",
    "GCPPubSubSource",
    "SyslogHECSource",
]
