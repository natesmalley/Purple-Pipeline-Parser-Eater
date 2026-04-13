"""OCSF field analyzer - extracts and validates OCSF field mappings from Lua code."""

import logging
import re
from typing import Dict, List, Any, Optional

from .ocsf_schema_registry import OCSFSchemaRegistry

logger = logging.getLogger(__name__)


class OCSFFieldAnalyzer:
    """Extracts OCSF fields from Lua code and validates against the schema registry."""

    _INTERNAL_DIAGNOSTIC_FIELDS = {"lua_error"}

    def __init__(self, registry: OCSFSchemaRegistry):
        self.registry = registry

    def analyze(self, lua_code: str, ocsf_version: str = "1.3.0") -> Dict[str, Any]:
        """
        Analyze Lua code for OCSF field mappings.

        Returns dict with detected fields, class info, coverage, and field details.
        """
        # Extract all field assignments
        fields_with_values = self._extract_fields(lua_code)
        detected_fields = [f["field"] for f in fields_with_values]

        # Detect class_uid
        class_uid = self._detect_class_uid(lua_code)
        class_name = None
        if class_uid:
            cls = self.registry.get_class(class_uid, ocsf_version)
            class_name = cls["class_name"] if cls else None

        # Validate against schema
        if class_uid:
            validation = self.registry.validate_fields(detected_fields, class_uid, ocsf_version)
        else:
            validation = {
                "required_present": [],
                "required_missing": [],
                "optional_present": [],
                "unknown_fields": detected_fields,
                "deprecated_fields": [],
                "coverage_pct": 0,
            }

        # Build field details
        field_details = self._build_field_details(
            fields_with_values, validation, class_uid, ocsf_version
        )

        return {
            "ocsf_version": ocsf_version,
            "class_uid": class_uid,
            "class_name": class_name,
            "detected_fields": detected_fields,
            "required_coverage": validation["coverage_pct"],
            "optional_coverage": self._calc_optional_coverage(validation, class_uid, ocsf_version),
            "missing_required": validation["required_missing"],
            "unknown_fields": validation["unknown_fields"],
            "deprecated_fields": validation["deprecated_fields"],
            "field_details": field_details,
            "semantic_signals": self._detect_semantic_signals(lua_code),
        }

    def _detect_semantic_signals(self, lua_code: str) -> Dict[str, Any]:
        """Extract semantic-quality signals used by score penalties."""
        placeholder_hits = re.findall(
            r'["\']Unknown(?:\s+[A-Za-z_]+)?["\']',
            lua_code,
            re.IGNORECASE,
        )
        has_unmapped_bucket = bool(
            re.search(r'["\']unmapped\.', lua_code) or
            re.search(r'\bunmapped\b', lua_code)
        )
        return {
            "placeholder_count": len(placeholder_hits),
            "placeholder_values": sorted(set(placeholder_hits)),
            "has_unmapped_bucket": has_unmapped_bucket,
        }

    def _extract_fields(self, lua_code: str) -> List[Dict[str, str]]:
        """Extract field assignments from Lua code."""
        fields = []
        seen = set()

        # Pattern 1: output.field = value / output["field"] = value / result.field = value
        for match in re.finditer(r'(?:output|result|ocsf|event)\.(\w[\w.]*)\s*=\s*([^\n]+)', lua_code):
            field = match.group(1)
            value = match.group(2).strip().rstrip(",")
            if field in self._INTERNAL_DIAGNOSTIC_FIELDS:
                continue
            # Skip 'log' prefix since it's the event wrapper, and skip sub-object init
            if field in ("log", "src_endpoint", "dst_endpoint", "metadata"):
                # But allow compound fields like src_endpoint.ip
                if "." not in field:
                    continue
            if field not in seen:
                fields.append({"field": field, "value": value})
                seen.add(field)

        # Pattern 1b: Bracket access: output["field"] = value / event["field"] = value
        for match in re.finditer(r'(?:output|result|ocsf|event)\["([^"]+)"\]\s*=\s*([^\n]+)', lua_code):
            field = match.group(1)
            value = match.group(2).strip().rstrip(",")
            if field in self._INTERNAL_DIAGNOSTIC_FIELDS:
                continue
            if field not in seen:
                fields.append({"field": field, "value": value})
                seen.add(field)

        # Pattern 3: Mapping table entries {type="computed"|"direct", target="field", ...}
        for match in re.finditer(
            r'\{[^}]*target\s*=\s*["\']([^"\']+)["\'][^}]*\}', lua_code
        ):
            field = match.group(1)
            if field in self._INTERNAL_DIAGNOSTIC_FIELDS:
                continue
            # Try to get the value
            value_match = re.search(r'value\s*=\s*([^,}]+)', match.group(0))
            value = value_match.group(1).strip() if value_match else ""
            if field not in seen:
                fields.append({"field": field, "value": value})
                seen.add(field)

        # Pattern 4: Local constants like OCSF_CLASS_UID = 3002 or CLASS_UID = 4001
        for match in re.finditer(r'local\s+(?:OCSF_)?(\w+)\s*=\s*(\d+)', lua_code):
            raw = match.group(1)
            value = match.group(2).strip()
            # Convert UPPER_CASE to lower_case ocsf field name
            field = raw.lower()
            # Only include if it looks like a known OCSF field
            ocsf_keywords = {"class_uid", "category_uid", "type_uid", "severity_id", "activity_id"}
            if field in ocsf_keywords and field not in seen:
                fields.append({"field": field, "value": value})
                seen.add(field)

        # Pattern 5: Table constructor style: { class_uid = 4001, category_uid = 4, ... }
        for match in re.finditer(r'(\w+)\s*=\s*(\d+|"[^"]*"|\'[^\']*\'|true|false)', lua_code):
            field = match.group(1)
            value = match.group(2).strip()
            # Only capture OCSF-looking fields inside table constructors
            ocsf_fields = {"class_uid", "category_uid", "type_uid", "severity_id",
                          "activity_id", "time", "class_name", "category_name",
                          "activity_name", "status_id"}
            if field in ocsf_fields and field not in seen:
                fields.append({"field": field, "value": value})
                seen.add(field)

        # Pattern 6: setNestedField(obj, "field", value) — canonical helper pattern
        for match in re.finditer(
            r'setNestedField\s*\([^,]+,\s*["\']([^"\']+)["\'],?\s*([^)]*)\)',
            lua_code
        ):
            field = match.group(1)
            value = match.group(2).strip().rstrip(",")
            if field in self._INTERNAL_DIAGNOSTIC_FIELDS:
                continue
            if field not in seen:
                fields.append({"field": field, "value": value})
                seen.add(field)

        # Pattern 7: Source field extraction from event access: event.field or event["field"]
        # (tracked as source_fields for coverage analysis)
        for match in re.finditer(r'event\[?"?\'?(\w[\w.]*)"?\'?\]?', lua_code):
            pass  # source fields tracked separately

        return fields

    def _detect_class_uid(self, lua_code: str) -> Optional[int]:
        """Detect the OCSF class_uid from Lua code."""
        # Direct assignment: class_uid = 4001 (including inside table constructors)
        match = re.search(r'class_uid\s*=\s*(\d+)', lua_code)
        if match:
            return int(match.group(1))

        # Local constant: local CLASS_UID = 4001 or OCSF_CLASS_UID = 4001
        match = re.search(r'(?:OCSF_)?CLASS_UID\s*=\s*(\d+)', lua_code)
        if match:
            return int(match.group(1))

        # Mapping table: target="class_uid" ... value=4001
        match = re.search(r'target\s*=\s*["\']class_uid["\'][^}]*value\s*=\s*(\d+)', lua_code)
        if match:
            return int(match.group(1))

        # Reverse order in mapping table: value=4001 ... target="class_uid"
        match = re.search(r'value\s*=\s*(\d+)[^}]*target\s*=\s*["\']class_uid["\']', lua_code)
        if match:
            return int(match.group(1))

        return None

    def _calc_optional_coverage(
        self, validation: Dict, class_uid: Optional[int], version: str
    ) -> float:
        if not class_uid:
            return 0
        cls = self.registry.get_class(class_uid, version)
        if not cls:
            return 0
        optional = set(cls["optional_fields"])
        if not optional:
            return 100
        present = len(validation["optional_present"])
        return round(present / len(optional) * 100, 1)

    def _build_field_details(
        self,
        fields_with_values: List[Dict],
        validation: Dict,
        class_uid: Optional[int],
        version: str,
    ) -> List[Dict[str, Any]]:
        """Build detailed field status list."""
        details = []
        required_set = set(validation["required_present"])
        optional_set = set(validation["optional_present"])
        unknown_set = set(validation["unknown_fields"])
        deprecated_set = set(validation["deprecated_fields"])

        for fv in fields_with_values:
            field = fv["field"]
            if field in required_set:
                status = "required_present"
            elif field in optional_set:
                status = "optional_present"
            elif field in deprecated_set:
                status = "deprecated"
            elif field in unknown_set:
                status = "unknown"
            else:
                status = "optional_present"  # not in any set but present

            details.append({
                "field": field,
                "status": status,
                "assigned_value": fv.get("value", ""),
            })

        # Add missing required fields
        for field in validation["required_missing"]:
            details.append({
                "field": field,
                "status": "required_missing",
                "assigned_value": None,
            })

        return details
