"""
Comprehensive S1 to Observo Field Mapping Database
Based on SentinelOne documentation, OCSF schemas, and Observo pipeline structures
"""
from typing import Dict, List
from components.s1_models import FieldMapping, S1DataType


# ============================================================================
# Core Field Mappings
# ============================================================================

CORE_FIELD_MAPPINGS: List[FieldMapping] = [
    # Timestamp fields
    FieldMapping(
        s1_field="timestamp",
        observo_field="@timestamp",
        ocsf_field="time",
        transformation="timestamp_ms_to_s",
        data_type_mapping={"s1": "DateTime", "observo": "timestamp"},
        notes="Primary event timestamp"
    ),
    FieldMapping(
        s1_field="createdAt",
        observo_field="created_time",
        ocsf_field="metadata.created_time",
        transformation="timestamp_ms_to_s",
        notes="Resource creation timestamp"
    ),
    FieldMapping(
        s1_field="updatedAt",
        observo_field="updated_time",
        ocsf_field="metadata.modified_time",
        transformation="timestamp_ms_to_s",
        notes="Resource update timestamp"
    ),

    # Identity fields
    FieldMapping(
        s1_field="user",
        observo_field="user.name",
        ocsf_field="actor.user.name",
        notes="Username"
    ),
    FieldMapping(
        s1_field="userId",
        observo_field="user.id",
        ocsf_field="actor.user.uid",
        notes="User identifier"
    ),
    FieldMapping(
        s1_field="userEmail",
        observo_field="user.email",
        ocsf_field="actor.user.email_addr",
        notes="User email address"
    ),

    # Host/Asset fields
    FieldMapping(
        s1_field="agentName",
        observo_field="host.name",
        ocsf_field="device.name",
        notes="Agent/host name"
    ),
    FieldMapping(
        s1_field="agentId",
        observo_field="host.id",
        ocsf_field="device.uid",
        notes="Agent unique identifier"
    ),
    FieldMapping(
        s1_field="agentIp",
        observo_field="host.ip",
        ocsf_field="device.ip",
        notes="Agent IP address"
    ),
    FieldMapping(
        s1_field="agentMacAddress",
        observo_field="host.mac",
        ocsf_field="device.mac",
        notes="Agent MAC address"
    ),
    FieldMapping(
        s1_field="osType",
        observo_field="host.os.type",
        ocsf_field="device.os.type",
        notes="Operating system type"
    ),
    FieldMapping(
        s1_field="osVersion",
        observo_field="host.os.version",
        ocsf_field="device.os.version",
        notes="Operating system version"
    ),

    # Process fields
    FieldMapping(
        s1_field="processName",
        observo_field="process.name",
        ocsf_field="process.name",
        notes="Process name"
    ),
    FieldMapping(
        s1_field="processId",
        observo_field="process.pid",
        ocsf_field="process.pid",
        data_type_mapping={"s1": "Integer", "observo": "long"},
        notes="Process ID"
    ),
    FieldMapping(
        s1_field="processPath",
        observo_field="process.executable",
        ocsf_field="process.file.path",
        notes="Process file path"
    ),
    FieldMapping(
        s1_field="processCommandLine",
        observo_field="process.command_line",
        ocsf_field="process.cmd_line",
        notes="Process command line"
    ),
    FieldMapping(
        s1_field="parentProcessName",
        observo_field="process.parent.name",
        ocsf_field="process.parent_process.name",
        notes="Parent process name"
    ),
    FieldMapping(
        s1_field="parentProcessId",
        observo_field="process.parent.pid",
        ocsf_field="process.parent_process.pid",
        data_type_mapping={"s1": "Integer", "observo": "long"},
        notes="Parent process ID"
    ),

    # Network fields
    FieldMapping(
        s1_field="srcIp",
        observo_field="source.ip",
        ocsf_field="src_endpoint.ip",
        notes="Source IP address"
    ),
    FieldMapping(
        s1_field="dstIp",
        observo_field="destination.ip",
        ocsf_field="dst_endpoint.ip",
        notes="Destination IP address"
    ),
    FieldMapping(
        s1_field="srcPort",
        observo_field="source.port",
        ocsf_field="src_endpoint.port",
        data_type_mapping={"s1": "Integer", "observo": "long"},
        notes="Source port"
    ),
    FieldMapping(
        s1_field="dstPort",
        observo_field="destination.port",
        ocsf_field="dst_endpoint.port",
        data_type_mapping={"s1": "Integer", "observo": "long"},
        notes="Destination port"
    ),
    FieldMapping(
        s1_field="protocol",
        observo_field="network.protocol",
        ocsf_field="connection_info.protocol_name",
        transformation="uppercase",
        notes="Network protocol"
    ),
    FieldMapping(
        s1_field="url",
        observo_field="url.full",
        ocsf_field="http_request.url.url_string",
        notes="Full URL"
    ),
    FieldMapping(
        s1_field="domain",
        observo_field="url.domain",
        ocsf_field="http_request.url.hostname",
        notes="Domain name"
    ),

    # File fields
    FieldMapping(
        s1_field="fileName",
        observo_field="file.name",
        ocsf_field="file.name",
        notes="File name"
    ),
    FieldMapping(
        s1_field="filePath",
        observo_field="file.path",
        ocsf_field="file.path",
        notes="File path"
    ),
    FieldMapping(
        s1_field="fileHash",
        observo_field="file.hash.sha256",
        ocsf_field="file.hashes[].value",
        notes="File hash (SHA256)"
    ),
    FieldMapping(
        s1_field="fileMd5",
        observo_field="file.hash.md5",
        ocsf_field="file.hashes[].value",
        notes="File hash (MD5)"
    ),
    FieldMapping(
        s1_field="fileSha1",
        observo_field="file.hash.sha1",
        ocsf_field="file.hashes[].value",
        notes="File hash (SHA1)"
    ),
    FieldMapping(
        s1_field="fileSize",
        observo_field="file.size",
        ocsf_field="file.size",
        data_type_mapping={"s1": "Long", "observo": "long"},
        notes="File size in bytes"
    ),

    # Threat/Security fields
    FieldMapping(
        s1_field="threatName",
        observo_field="threat.name",
        ocsf_field="malware.name",
        notes="Threat name"
    ),
    FieldMapping(
        s1_field="threatClassification",
        observo_field="threat.category",
        ocsf_field="malware.classification",
        notes="Threat classification"
    ),
    FieldMapping(
        s1_field="threatSeverity",
        observo_field="event.severity",
        ocsf_field="severity_id",
        transformation="lowercase",
        notes="Threat severity level"
    ),
    FieldMapping(
        s1_field="mitreTechnique",
        observo_field="threat.technique.id",
        ocsf_field="attacks[].technique.uid",
        notes="MITRE ATT&CK technique ID"
    ),
    FieldMapping(
        s1_field="mitreTactic",
        observo_field="threat.tactic.id",
        ocsf_field="attacks[].tactic.uid",
        notes="MITRE ATT&CK tactic ID"
    ),

    # Event fields
    FieldMapping(
        s1_field="eventType",
        observo_field="event.type",
        ocsf_field="class_name",
        notes="Event type"
    ),
    FieldMapping(
        s1_field="eventId",
        observo_field="event.id",
        ocsf_field="metadata.uid",
        notes="Event unique identifier"
    ),
    FieldMapping(
        s1_field="message",
        observo_field="message",
        ocsf_field="message",
        notes="Event message"
    ),
    FieldMapping(
        s1_field="description",
        observo_field="event.description",
        ocsf_field="finding.desc",
        notes="Event description"
    ),

    # Cloud fields
    FieldMapping(
        s1_field="cloudProvider",
        observo_field="cloud.provider",
        ocsf_field="cloud.provider",
        transformation="lowercase",
        notes="Cloud provider (aws, azure, gcp)"
    ),
    FieldMapping(
        s1_field="cloudAccount",
        observo_field="cloud.account.id",
        ocsf_field="cloud.account.uid",
        notes="Cloud account ID"
    ),
    FieldMapping(
        s1_field="cloudRegion",
        observo_field="cloud.region",
        ocsf_field="cloud.region",
        notes="Cloud region"
    ),
    FieldMapping(
        s1_field="cloudResourceId",
        observo_field="cloud.instance.id",
        ocsf_field="cloud.resource_uid",
        notes="Cloud resource ID"
    ),

    # Vulnerability fields
    FieldMapping(
        s1_field="cveId",
        observo_field="vulnerability.id",
        ocsf_field="vulnerabilities[].cve.uid",
        notes="CVE identifier"
    ),
    FieldMapping(
        s1_field="cveScore",
        observo_field="vulnerability.score.base",
        ocsf_field="vulnerabilities[].cve.cvss[].base_score",
        data_type_mapping={"s1": "Float", "observo": "float"},
        notes="CVE score"
    ),
    FieldMapping(
        s1_field="vulnerabilitySeverity",
        observo_field="vulnerability.severity",
        ocsf_field="severity",
        notes="Vulnerability severity"
    ),
]


# ============================================================================
# Deep Visibility Specific Mappings
# ============================================================================

DEEP_VISIBILITY_MAPPINGS: List[FieldMapping] = [
    FieldMapping(
        s1_field="ObjectType",
        observo_field="event.category",
        ocsf_field="category_name",
        notes="Deep Visibility object type"
    ),
    FieldMapping(
        s1_field="EventType",
        observo_field="event.action",
        ocsf_field="activity_name",
        notes="Deep Visibility event type"
    ),
    FieldMapping(
        s1_field="SrcProcName",
        observo_field="process.name",
        ocsf_field="process.name",
        notes="Source process name"
    ),
    FieldMapping(
        s1_field="TgtProcName",
        observo_field="process.target.name",
        ocsf_field="dst_endpoint.process.name",
        notes="Target process name"
    ),
    FieldMapping(
        s1_field="SrcProcCmdLine",
        observo_field="process.command_line",
        ocsf_field="process.cmd_line",
        notes="Source process command line"
    ),
    FieldMapping(
        s1_field="TgtFilePath",
        observo_field="file.path",
        ocsf_field="file.path",
        notes="Target file path"
    ),
    FieldMapping(
        s1_field="SrcProcUser",
        observo_field="user.name",
        ocsf_field="actor.user.name",
        notes="Source process user"
    ),
]


# ============================================================================
# Vulnerability Management Mappings
# ============================================================================

VULNERABILITY_MAPPINGS: List[FieldMapping] = [
    FieldMapping(
        s1_field="software.name",
        observo_field="package.name",
        ocsf_field="vulnerabilities[].kb_articles[].product",
        notes="Vulnerable software name"
    ),
    FieldMapping(
        s1_field="software.version",
        observo_field="package.version",
        ocsf_field="vulnerabilities[].kb_articles[].version",
        notes="Vulnerable software version"
    ),
    FieldMapping(
        s1_field="software.vendor",
        observo_field="package.vendor",
        ocsf_field="vulnerabilities[].vendor_name",
        notes="Software vendor"
    ),
    FieldMapping(
        s1_field="software.fixVersion",
        observo_field="package.fixed_version",
        ocsf_field="vulnerabilities[].fix_available",
        notes="Version with fix"
    ),
    FieldMapping(
        s1_field="cve.publishedDate",
        observo_field="vulnerability.published_at",
        ocsf_field="vulnerabilities[].cve.created_time",
        transformation="timestamp_ms_to_s",
        notes="CVE published date"
    ),
    FieldMapping(
        s1_field="cve.exploitedInTheWild",
        observo_field="vulnerability.exploit.in_the_wild",
        ocsf_field="vulnerabilities[].is_exploit",
        transformation="bool_to_int",
        notes="Exploit in the wild status"
    ),
    FieldMapping(
        s1_field="cve.epssScore",
        observo_field="vulnerability.epss.score",
        ocsf_field="vulnerabilities[].cve.epss_score",
        data_type_mapping={"s1": "Float", "observo": "float"},
        notes="EPSS score"
    ),
]


# ============================================================================
# Aggregation Function Mappings
# ============================================================================

AGGREGATION_MAPPINGS: Dict[str, str] = {
    # S1 -> Observo
    "COUNT": "count",
    "SUM": "sum",
    "AVG": "avg",
    "MIN": "min",
    "MAX": "max",
    "DISTINCT": "cardinality",
    "UNIQUE": "cardinality",
    "PERCENTILE": "percentiles",
    "STDDEV": "extended_stats",
}


# ============================================================================
# Operator Mappings
# ============================================================================

OPERATOR_MAPPINGS: Dict[str, str] = {
    # S1 -> Observo/Lua
    "=": "==",
    "!=": "~=",
    ">": ">",
    "<": "<",
    ">=": ">=",
    "<=": "<=",
    "CONTAINS": "contains",
    "STARTSWITH": "startswith",
    "ENDSWITH": "endswith",
    "IN": "in_list",
    "NOT IN": "not_in_list",
    "LIKE": "match",
    "MATCHES": "match_regex",
    "EXISTS": "exists",
    "NOT EXISTS": "not_exists",
    "IS NULL": "is_nil",
    "IS NOT NULL": "not_nil",
}


# ============================================================================
# Helper Functions
# ============================================================================

def get_mapping_by_s1_field(s1_field: str) -> FieldMapping:
    """
    Get field mapping by S1 field name

    Args:
        s1_field: SentinelOne field name

    Returns:
        FieldMapping or None if not found
    """
    all_mappings = CORE_FIELD_MAPPINGS + DEEP_VISIBILITY_MAPPINGS + VULNERABILITY_MAPPINGS

    for mapping in all_mappings:
        if mapping.s1_field == s1_field:
            return mapping

    return None


def get_mapping_by_observo_field(observo_field: str) -> FieldMapping:
    """
    Get field mapping by Observo field name

    Args:
        observo_field: Observo field name

    Returns:
        FieldMapping or None if not found
    """
    all_mappings = CORE_FIELD_MAPPINGS + DEEP_VISIBILITY_MAPPINGS + VULNERABILITY_MAPPINGS

    for mapping in all_mappings:
        if mapping.observo_field == observo_field:
            return mapping

    return None


def get_all_mappings() -> List[FieldMapping]:
    """Get all field mappings"""
    return CORE_FIELD_MAPPINGS + DEEP_VISIBILITY_MAPPINGS + VULNERABILITY_MAPPINGS


def get_mappings_by_category(category: str) -> List[FieldMapping]:
    """
    Get field mappings by category

    Args:
        category: Category (core, deep_visibility, vulnerability)

    Returns:
        List of field mappings
    """
    if category == "core":
        return CORE_FIELD_MAPPINGS
    elif category == "deep_visibility":
        return DEEP_VISIBILITY_MAPPINGS
    elif category == "vulnerability":
        return VULNERABILITY_MAPPINGS
    else:
        return get_all_mappings()


def map_s1_to_observo(s1_field: str, s1_value: any) -> tuple:
    """
    Map S1 field and value to Observo format

    Args:
        s1_field: S1 field name
        s1_value: S1 field value

    Returns:
        Tuple of (observo_field, observo_value)
    """
    mapping = get_mapping_by_s1_field(s1_field)

    if mapping:
        observo_field = mapping.observo_field
        observo_value = mapping.apply_transformation(s1_value)
        return observo_field, observo_value
    else:
        # No mapping found, return original
        return s1_field, s1_value


def map_operator(s1_operator: str) -> str:
    """
    Map S1 operator to Observo/Lua operator

    Args:
        s1_operator: S1 operator

    Returns:
        Observo/Lua operator
    """
    return OPERATOR_MAPPINGS.get(s1_operator, s1_operator)


def map_aggregation(s1_aggregation: str) -> str:
    """
    Map S1 aggregation function to Observo aggregation

    Args:
        s1_aggregation: S1 aggregation function

    Returns:
        Observo aggregation function
    """
    return AGGREGATION_MAPPINGS.get(s1_aggregation.upper(), s1_aggregation.lower())
