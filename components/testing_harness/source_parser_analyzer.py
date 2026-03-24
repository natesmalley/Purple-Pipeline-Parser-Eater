"""Source parser field analyzer - extracts field inventories from SentinelOne parser configs."""

import logging
import re
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class SourceParserAnalyzer:
    """Analyzes source parser configurations to extract field inventories."""

    def analyze_parser(self, parser_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract all fields from a parser configuration.

        Supports multiple config structures from the ai-siem repo.
        """
        fields: List[Dict[str, Any]] = []
        seen = set()

        parser_name = (
            parser_config.get("parser_name")
            or parser_config.get("parser_id")
            or "unknown"
        )

        # Extract vendor/product
        attrs = parser_config.get("config", parser_config).get("attributes", {})
        ds = attrs.get("dataSource", {})
        vendor = ds.get("vendor")
        product = ds.get("product")

        # Source 1: config.mappings.mappings
        mappings = parser_config.get("config", parser_config).get("mappings", {})
        if isinstance(mappings, dict):
            mapping_list = mappings.get("mappings", [])
        elif isinstance(mappings, list):
            mapping_list = mappings
        else:
            mapping_list = []

        for m in mapping_list:
            if isinstance(m, dict) and "name" in m:
                name = m["name"]
                if name not in seen:
                    fields.append({
                        "name": name,
                        "type": m.get("type"),
                        "source": "mappings",
                    })
                    seen.add(name)

        # Source 2: config.fields
        config_fields = parser_config.get("config", parser_config).get("fields", [])
        for f in config_fields:
            if isinstance(f, dict) and "name" in f:
                name = f["name"]
                if name not in seen:
                    fields.append({
                        "name": name,
                        "type": f.get("type"),
                        "source": "fields",
                    })
                    seen.add(name)
            elif isinstance(f, str) and f not in seen:
                fields.append({"name": f, "type": None, "source": "fields"})
                seen.add(f)

        # Source 3: field_schema.fields
        schema_fields = parser_config.get("field_schema", {}).get("fields", [])
        for f in schema_fields:
            if isinstance(f, dict) and "name" in f:
                name = f["name"]
                if name not in seen:
                    fields.append({
                        "name": name,
                        "type": f.get("type"),
                        "source": "field_schema",
                    })
                    seen.add(name)

        # Source 4: patterns (grok)
        patterns = parser_config.get("config", parser_config).get("patterns", [])
        for p in patterns:
            if isinstance(p, str):
                for m in re.findall(r'%\{[^:]+:(\w+)\}', p):
                    if m not in seen:
                        fields.append({"name": m, "type": None, "source": "grok_pattern"})
                        seen.add(m)

        # Source 5: serialization_components mapping tables
        proc_profile = parser_config.get("processing_profile", {})
        if isinstance(proc_profile, dict):
            ser_components = proc_profile.get("serialization_components", [])
            for comp in ser_components:
                if not isinstance(comp, dict):
                    continue
                config = comp.get("config", {})
                if not isinstance(config, dict):
                    continue
                groups = config.get("config_groups", [])
                for group in groups:
                    if isinstance(group, dict) and "script" in group:
                        script = group["script"]
                        # Extract field references from mapping tables
                        for m in re.finditer(
                            r'source\s*=\s*["\']([^"\']+)["\']', str(script)
                        ):
                            name = m.group(1)
                            if name not in seen:
                                fields.append({
                                    "name": name,
                                    "type": None,
                                    "source": "serialization_script",
                                })
                                seen.add(name)

        fmt = None
        formats = parser_config.get("config", parser_config).get("formats", [])
        if formats and isinstance(formats[0], dict):
            fmt = formats[0].get("format")

        return {
            "parser_name": parser_name,
            "vendor": vendor,
            "product": product,
            "total_fields": len(fields),
            "fields": fields,
            "format": fmt,
        }

    def compare_with_lua(
        self, parser_fields: Dict[str, Any], lua_code: str
    ) -> Dict[str, Any]:
        """
        Compare source parser fields against Lua code field references.
        """
        source_names = set()
        if isinstance(parser_fields, dict):
            for f in parser_fields.get("fields", []):
                if isinstance(f, dict):
                    source_names.add(f["name"])
                elif isinstance(f, str):
                    source_names.add(f)

        lua_fields = self._extract_lua_fields(lua_code)

        # Normalize field names for comparison (lowercase, strip dots)
        source_norm = {self._normalize(n): n for n in source_names}
        lua_norm = {self._normalize(n): n for n in lua_fields}

        mapped = []
        unmapped_source = []
        for norm, original in source_norm.items():
            if norm in lua_norm:
                mapped.append({"source": original, "lua_reference": lua_norm[norm]})
            else:
                # Fuzzy: check if any lua field contains the source field name
                found = False
                for ln, lo in lua_norm.items():
                    if norm in ln or ln in norm:
                        mapped.append({"source": original, "lua_reference": lo})
                        found = True
                        break
                if not found:
                    unmapped_source.append(original)

        new_lua = sorted(
            lua_fields - {m["lua_reference"] for m in mapped}
        )

        coverage = (len(mapped) / len(source_names) * 100) if source_names else 100

        return {
            "source_field_count": len(source_names),
            "lua_field_count": len(lua_fields),
            "all_lua_fields": sorted(lua_fields),
            "mapped_fields": mapped,
            "unmapped_source_fields": unmapped_source,
            "new_lua_fields": new_lua,
            "coverage_pct": round(coverage, 1),
        }

    def get_field_inventory(self, parser_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convenience: return just the field list."""
        result = self.analyze_parser(parser_config)
        return result["fields"]

    def _extract_lua_fields(self, lua_code: str) -> set:
        """Extract field references from Lua code."""
        fields = set()

        # event["field"] / event['field'] / record["field"]
        for m in re.findall(r'(?:event|record)\[["\']([\w.]+)["\']\]', lua_code):
            fields.add(m)

        # event.field / record.field
        for m in re.findall(r'(?:event|record)\.([\w]+)', lua_code):
            fields.add(m)

        # output.field = ...
        for m in re.findall(r'output\.([\w.]+)\s*=', lua_code):
            fields.add(m)

        # Mapping source references
        for m in re.findall(r'source\s*=\s*["\']([^"\']+)["\']', lua_code):
            fields.add(m)

        # Mapping target references
        for m in re.findall(r'target\s*=\s*["\']([^"\']+)["\']', lua_code):
            fields.add(m)

        return fields

    def _normalize(self, name: str) -> str:
        """Normalize a field name for fuzzy comparison."""
        return name.lower().replace(".", "_").replace("-", "_")
