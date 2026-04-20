"""OCSF Schema Registry - multi-version schema definitions for field validation."""

import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class OCSFSchemaRegistry:
    """Built-in OCSF schema registry with multi-version support."""

    def __init__(self):
        self._schemas = self._build_schemas()

    def list_versions(self) -> List[str]:
        return sorted(self._schemas.keys())

    def list_classes(self, version: str = "1.3.0") -> List[Dict[str, Any]]:
        schema = self._schemas.get(version, {})
        return [
            {
                "class_uid": uid,
                "class_name": cls["class_name"],
                "category_uid": cls["category_uid"],
                "category_name": cls["category_name"],
            }
            for uid, cls in sorted(schema.items())
        ]

    def get_class(self, class_uid: int, version: str = "1.3.0") -> Optional[Dict]:
        return self._schemas.get(version, {}).get(class_uid)

    def get_required_fields(self, class_uid: Optional[int], version: str = "1.3.0") -> List[str]:
        if class_uid is None:
            # Return common OCSF required fields
            return ["class_uid", "category_uid", "activity_id", "time", "type_uid", "severity_id"]
        cls = self.get_class(class_uid, version)
        return cls["required_fields"] if cls else []

    def get_all_fields(self, class_uid: int, version: str = "1.3.0") -> List[str]:
        cls = self.get_class(class_uid, version)
        if not cls:
            return []
        return cls["required_fields"] + cls["optional_fields"]

    def get_field_type(self, class_uid: int, field_path: str, version: str = "1.3.0") -> Optional[str]:
        cls = self.get_class(class_uid, version)
        if not cls:
            return None
        return cls.get("field_types", {}).get(field_path)

    def validate_fields(
        self, fields: List[str], class_uid: int, version: str = "1.3.0"
    ) -> Dict[str, Any]:
        cls = self.get_class(class_uid, version)
        if not cls:
            return {
                "error": f"Class {class_uid} not found in OCSF {version}",
                "required_present": [], "required_missing": [],
                "optional_present": [], "unknown_fields": [],
                "deprecated_fields": [], "coverage_pct": 0,
            }

        required = set(cls["required_fields"])
        optional = set(cls["optional_fields"])
        deprecated = set(cls.get("deprecated_fields", []))
        field_set = set(fields)

        req_present = sorted(field_set & required)
        req_missing = sorted(required - field_set)
        opt_present = sorted(field_set & optional)
        unknown = sorted(field_set - required - optional - deprecated)
        dep_found = sorted(field_set & deprecated)

        coverage = (len(req_present) / len(required) * 100) if required else 100

        return {
            "required_present": req_present,
            "required_missing": req_missing,
            "optional_present": opt_present,
            "unknown_fields": unknown,
            "deprecated_fields": dep_found,
            "coverage_pct": round(coverage, 1),
        }

    def _build_schemas(self) -> Dict[str, Dict[int, Dict]]:
        """Build OCSF schema definitions for all supported versions."""
        # Base fields common to all event classes
        base_required = ["class_uid", "category_uid", "activity_id", "time", "type_uid", "severity_id"]
        base_optional = [
            "message", "raw_data", "status", "status_id", "status_detail",
            "count", "duration", "start_time", "end_time", "timezone_offset",
            "metadata.product.name", "metadata.product.vendor_name", "metadata.version",
        ]
        base_types = {
            "class_uid": "integer", "category_uid": "integer", "activity_id": "integer",
            "time": "long", "type_uid": "long", "severity_id": "integer",
            "message": "string", "status": "string", "status_id": "integer",
            "count": "integer", "duration": "long",
        }

        classes_v1_0 = {
            1001: {
                "class_name": "File Activity",
                "category_uid": 1, "category_name": "System Activity",
                "required_fields": base_required,
                "optional_fields": base_optional + [
                    "file.name", "file.path", "file.size", "file.type_id",
                    "file.hashes", "file.owner.name",
                    "actor.user.name", "actor.user.uid", "actor.process.name",
                    "device.hostname", "device.ip", "device.os.name",
                ],
                "field_types": {**base_types, "file.size": "long", "file.type_id": "integer"},
            },
            1007: {
                "class_name": "Process Activity",
                "category_uid": 1, "category_name": "System Activity",
                "required_fields": base_required,
                "optional_fields": base_optional + [
                    "process.name", "process.pid", "process.cmd_line",
                    "process.file.path", "process.file.name",
                    "process.uid", "process.user.name",
                    "actor.user.name", "actor.process.name", "actor.process.pid",
                    "device.hostname", "device.ip", "device.os.name",
                    "parent_process.name", "parent_process.pid",
                ],
                "field_types": {**base_types, "process.pid": "integer"},
            },
            2004: {
                "class_name": "Detection Finding",
                "category_uid": 2, "category_name": "Findings",
                "required_fields": base_required + ["finding_info.title", "finding_info.uid"],
                "optional_fields": base_optional + [
                    "finding_info.desc", "finding_info.types",
                    "finding_info.created_time", "finding_info.modified_time",
                    "confidence_id", "impact_id", "risk_level_id",
                    "evidences", "remediation", "resources",
                    "src_url", "attacks",
                ],
                "field_types": {**base_types, "confidence_id": "integer", "impact_id": "integer"},
            },
            3002: {
                "class_name": "Authentication",
                "category_uid": 3, "category_name": "Identity & Access Management",
                "required_fields": base_required,
                "optional_fields": base_optional + [
                    "actor.user.name", "actor.user.uid", "actor.user.domain",
                    "src_endpoint.ip", "src_endpoint.hostname", "src_endpoint.port",
                    "dst_endpoint.ip", "dst_endpoint.hostname", "dst_endpoint.port",
                    "user.name", "user.uid", "user.email_addr",
                    "auth_protocol", "auth_protocol_id", "is_mfa",
                    "service.name", "service.uid",
                    "session.uid", "session.issuer",
                    "http_request.url", "http_request.user_agent",
                ],
                "field_types": {**base_types, "is_mfa": "boolean", "auth_protocol_id": "integer"},
            },
            4001: {
                "class_name": "Network Activity",
                "category_uid": 4, "category_name": "Network Activity",
                "required_fields": base_required,
                "optional_fields": base_optional + [
                    "src_endpoint.ip", "src_endpoint.port", "src_endpoint.hostname",
                    "dst_endpoint.ip", "dst_endpoint.port", "dst_endpoint.hostname",
                    "protocol_name", "protocol_ver",
                    "bytes_in", "bytes_out", "packets_in", "packets_out",
                    "direction_id", "action_id",
                    "tls.version", "tls.cipher",
                    "connection_info.uid", "connection_info.protocol_name",
                ],
                "field_types": {
                    **base_types, "bytes_in": "long", "bytes_out": "long",
                    "direction_id": "integer", "action_id": "integer",
                },
            },
            4002: {
                "class_name": "HTTP Activity",
                "category_uid": 4, "category_name": "Network Activity",
                "required_fields": base_required,
                "optional_fields": base_optional + [
                    "http_request.url", "http_request.http_method",
                    "http_request.user_agent", "http_request.referrer",
                    "http_request.version",
                    "http_response.code", "http_response.message",
                    "http_response.content_type", "http_response.length",
                    "src_endpoint.ip", "src_endpoint.port",
                    "dst_endpoint.ip", "dst_endpoint.port", "dst_endpoint.hostname",
                    "tls.version",
                ],
                "field_types": {**base_types, "http_response.code": "integer"},
            },
            4003: {
                "class_name": "DNS Activity",
                "category_uid": 4, "category_name": "Network Activity",
                "required_fields": base_required,
                "optional_fields": base_optional + [
                    "query.hostname", "query.type", "query.class",
                    "answers", "rcode", "rcode_id",
                    "src_endpoint.ip", "src_endpoint.port",
                    "dst_endpoint.ip", "dst_endpoint.port",
                    "connection_info.protocol_name",
                ],
                "field_types": {**base_types, "rcode_id": "integer"},
            },
            2001: {
                "class_name": "Security Finding",
                "category_uid": 2, "category_name": "Findings",
                "required_fields": base_required + ["finding_info.title", "finding_info.uid"],
                "optional_fields": base_optional + [
                    "finding_info.desc", "finding_info.types",
                    "finding_info.src_url", "finding_info.created_time",
                    "confidence_id", "impact_id", "risk_level_id", "risk_score",
                    "evidences", "remediation", "resources", "vulnerabilities",
                    "device.hostname", "device.ip", "device.os.name",
                    "activity_name", "class_name", "category_name",
                ],
                "field_types": {**base_types, "confidence_id": "integer", "impact_id": "integer", "risk_score": "float"},
            },
            2002: {
                "class_name": "Vulnerability Finding",
                "category_uid": 2, "category_name": "Findings",
                "required_fields": base_required + ["finding_info.title", "finding_info.uid"],
                "optional_fields": base_optional + [
                    "finding_info.desc", "finding_info.types", "finding_info.src_url",
                    "finding_info.created_time", "finding_info.modified_time",
                    "finding_info.first_seen_time", "finding_info.last_seen_time",
                    "vulnerabilities", "vulnerabilities.cve.uid", "vulnerabilities.severity",
                    "vulnerabilities.cvss", "vulnerabilities.affected_packages",
                    "vulnerabilities.references", "vulnerabilities.is_fix_available",
                    "resources", "resources.name", "resources.uid", "resources.type",
                    "remediation.desc",
                ],
                "field_types": {**base_types},
            },
            3001: {
                "class_name": "Account Change",
                "category_uid": 3, "category_name": "Identity & Access Management",
                "required_fields": base_required,
                "optional_fields": base_optional + [
                    "user.name", "user.uid", "user.email_addr", "user.full_name", "user.type",
                    "actor.user.name", "actor.user.uid", "actor.user.full_name",
                    "src_endpoint.ip", "src_endpoint.hostname",
                    "cloud.account.uid", "cloud.account.type", "cloud.provider",
                    "enrichments",
                ],
                "field_types": {**base_types},
            },
            5001: {
                "class_name": "Device Inventory Info",
                "category_uid": 5, "category_name": "Discovery",
                "required_fields": base_required + ["device.uid"],
                "optional_fields": base_optional + [
                    "device.name", "device.hostname", "device.ip", "device.type",
                    "device.os.name", "device.os.type",
                    "device.agent_list", "device.groups", "device.location.desc",
                    "metadata.event_code", "metadata.log_name",
                ],
                "field_types": {**base_types},
            },
            6001: {
                "class_name": "Web Resources Activity",
                "category_uid": 6, "category_name": "Application Activity",
                "required_fields": base_required,
                "optional_fields": base_optional + [
                    "web_resources.type", "web_resources.url", "web_resources.desc",
                    "http_request.url", "http_request.http_method",
                    "http_request.user_agent", "http_response.code",
                    "src_endpoint.ip", "src_endpoint.port",
                    "dst_endpoint.ip", "dst_endpoint.hostname",
                    "actor.user.name", "actor.user.uid",
                    "activity_name", "class_name", "category_name",
                    "device.hostname", "device.ip",
                ],
                "field_types": {**base_types, "http_response.code": "integer"},
            },
            6003: {
                "class_name": "API Activity",
                "category_uid": 6, "category_name": "Application Activity",
                "required_fields": base_required,
                "optional_fields": base_optional + [
                    "api.operation", "api.service.name", "api.version",
                    "api.request.uid", "api.response.code", "api.response.error",
                    "actor.user.name", "actor.user.uid", "actor.user.account.uid",
                    "src_endpoint.ip", "src_endpoint.domain",
                    "resources", "cloud.provider", "cloud.region", "cloud.account.uid",
                    "http_request.url", "http_request.http_method", "http_request.user_agent",
                    "activity_name", "class_name", "category_name",
                    "device.hostname", "device.ip",
                    "connection_info.protocol_name", "connection_info.uid",
                ],
                "field_types": {**base_types, "api.response.code": "integer"},
            },
        }

        # v1.1.0: adds observables, unmapped, metadata.log_name
        classes_v1_1 = {}
        for uid, cls in classes_v1_0.items():
            c = {**cls}
            c["optional_fields"] = list(cls["optional_fields"]) + [
                "observables", "unmapped", "metadata.log_name",
            ]
            classes_v1_1[uid] = c

        # v1.3.0: adds enrichments, metadata.profiles, risk_score
        classes_v1_3 = {}
        for uid, cls in classes_v1_1.items():
            c = {**cls}
            c["optional_fields"] = list(cls["optional_fields"]) + [
                "enrichments", "metadata.profiles",
            ]
            if uid == 2004:
                c["optional_fields"].append("risk_score")
                c["deprecated_fields"] = ["risk_level_id"]
            classes_v1_3[uid] = c

        return {
            "1.0.0": classes_v1_0,
            "1.1.0": classes_v1_1,
            "1.3.0": classes_v1_3,
        }
