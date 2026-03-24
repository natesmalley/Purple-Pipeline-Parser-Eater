"""Test event builder - generates realistic test events based on parser metadata."""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


class TestEventBuilder:
    """Generates realistic test events for parser validation."""

    def build_events(self, parser_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate 4 test events based on parser field inventory.

        Args:
            parser_info: Output from SourceParserAnalyzer.analyze_parser()

        Returns:
            List of test event dicts with name, description, event, expected_behavior.
        """
        fields = parser_info.get("fields", [])
        vendor = parser_info.get("vendor", "Unknown")
        product = parser_info.get("product", "Unknown")
        parser_name = parser_info.get("parser_name", "unknown")

        return [
            self._build_happy_path(fields, vendor, product, parser_name),
            self._build_minimal(fields, vendor, product, parser_name),
            self._build_edge_case(fields, vendor, product, parser_name),
            self._build_error_case(fields, vendor, product, parser_name),
        ]

    def build_custom_event(self, fields: Dict[str, Any]) -> Dict[str, Any]:
        """Wrap a user-provided dict in the standard test event format."""
        return {
            "name": "Custom Event",
            "description": "User-provided test event",
            "event": fields,
            "expected_behavior": "User-defined",
        }

    def _build_happy_path(
        self, fields: List[Dict], vendor: str, product: str, parser_name: str
    ) -> Dict[str, Any]:
        event = {}
        for f in fields:
            name = f.get("name", "")
            ftype = f.get("type")
            event[name] = self._generate_value(name, ftype, "happy")

        # Ensure basic fields
        event.setdefault("timestamp", datetime.utcnow().isoformat() + "Z")
        event.setdefault("vendor", vendor)
        event.setdefault("product", product)

        return {
            "name": "Happy Path",
            "description": f"All {len(fields)} fields populated with realistic values",
            "event": event,
            "expected_behavior": "All fields should map to OCSF output correctly",
        }

    def _build_minimal(
        self, fields: List[Dict], vendor: str, product: str, parser_name: str
    ) -> Dict[str, Any]:
        # Only include fields that look required
        required_hints = {"timestamp", "time", "event_id", "event_type", "source", "id", "type"}
        event = {}
        for f in fields:
            name = f.get("name", "")
            name_lower = name.lower()
            if any(h in name_lower for h in required_hints):
                event[name] = self._generate_value(name, f.get("type"), "happy")

        event.setdefault("timestamp", datetime.utcnow().isoformat() + "Z")

        return {
            "name": "Minimal",
            "description": f"Only {len(event)} likely-required fields",
            "event": event,
            "expected_behavior": "Should produce valid OCSF output with missing optional fields",
        }

    def _build_edge_case(
        self, fields: List[Dict], vendor: str, product: str, parser_name: str
    ) -> Dict[str, Any]:
        event = {}
        for f in fields:
            name = f.get("name", "")
            ftype = f.get("type")
            event[name] = self._generate_value(name, ftype, "edge")

        return {
            "name": "Edge Case",
            "description": "Fields with special characters, long strings, unicode",
            "event": event,
            "expected_behavior": "Should handle edge cases without errors",
        }

    def _build_error_case(
        self, fields: List[Dict], vendor: str, product: str, parser_name: str
    ) -> Dict[str, Any]:
        event = {}
        for f in fields:
            name = f.get("name", "")
            ftype = f.get("type")
            event[name] = self._generate_value(name, ftype, "error")

        # Remove some critical fields
        for key in ["timestamp", "time", "event_id"]:
            event.pop(key, None)

        return {
            "name": "Error Case",
            "description": "Missing critical fields and malformed values",
            "event": event,
            "expected_behavior": "Should handle errors gracefully without crashing",
        }

    def _generate_value(self, field_name: str, field_type: str = None, mode: str = "happy") -> Any:
        """Generate a value based on field name pattern and mode."""
        name = field_name.lower()

        if mode == "edge":
            return self._edge_value(name, field_type)
        if mode == "error":
            return self._error_value(name, field_type)

        # Happy path value generation
        if any(k in name for k in ("timestamp", "time", "date", "_at")):
            return (datetime.utcnow() - timedelta(minutes=5)).isoformat() + "Z"
        if name in ("src_ip", "source_ip", "srcip") or name.endswith("_ip") and "src" in name:
            return "10.10.10.5"
        if name in ("dst_ip", "dest_ip", "dstip") or name.endswith("_ip") and "dst" in name:
            return "192.168.1.10"
        if "ip" in name:
            return "172.16.0.50"
        if "port" in name:
            return 443
        if any(k in name for k in ("user_name", "username", "user.name")):
            return "admin@corp.local"
        if "email" in name:
            return "admin@example.com"
        if "host" in name:
            return "server-01.corp.local"
        if name in ("event_id", "eventid"):
            return 4624
        if "uid" in name or "uuid" in name:
            return str(uuid.uuid4())
        if "url" in name or "uri" in name:
            return "https://app.example.com/api/v1/resource"
        if "path" in name:
            return "/var/log/auth.log"
        if "status" in name:
            return "success"
        if "severity" in name or "level" in name:
            return "medium"
        if any(k in name for k in ("message", "msg", "description", "desc")):
            return f"Sample event from {field_name}"
        if "action" in name:
            return "allow"
        if "protocol" in name:
            return "tcp"
        if "domain" in name:
            return "corp.local"
        if "pid" in name:
            return 12345
        if "cmd" in name or "command" in name:
            return "/usr/bin/ssh -l admin 10.10.10.5"
        if "name" in name:
            return f"sample-{field_name}"
        if "size" in name or "bytes" in name or "length" in name:
            return 1024

        # Type-based fallback
        if field_type in ("long", "int", "integer"):
            return 42
        if field_type == "boolean":
            return True
        if field_type == "ip":
            return "10.0.0.1"
        if field_type == "date":
            return datetime.utcnow().isoformat() + "Z"

        return f"sample_{field_name}"

    def _edge_value(self, name: str, field_type: str = None) -> Any:
        """Generate edge-case values."""
        if "ip" in name:
            return "::ffff:192.168.1.1"  # IPv6-mapped IPv4
        if any(k in name for k in ("timestamp", "time", "date")):
            return "2024-01-15T10:30:00.123456789+05:30"
        if any(k in name for k in ("message", "msg", "desc")):
            return "Event with <html>&amp;special</html> chars: \u00e9\u00e8\u00ea \u2603 \ud83d\ude00 " + "A" * 500
        if "name" in name or "user" in name:
            return "user@domain.com; DROP TABLE events;--"
        if "path" in name:
            return "/var/log/../../../etc/passwd"
        if field_type in ("long", "int", "integer"):
            return 2147483647  # max int32
        return "edge_\u00e9\u00e8\u00ea_value"

    def _error_value(self, name: str, field_type: str = None) -> Any:
        """Generate error-case values."""
        if "ip" in name:
            return "not.an.ip.address"
        if any(k in name for k in ("timestamp", "time", "date")):
            return "not-a-timestamp"
        if field_type in ("long", "int", "integer"):
            return "not_a_number"
        if "port" in name:
            return -1
        return None
