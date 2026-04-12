"""Source parser field analyzer - extracts field inventories from SentinelOne parser configs."""

import logging
import re
import json
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

        # Source 6: raw/historical examples (critical for custom parser-from-samples flows)
        for name in self._extract_fields_from_examples(
            parser_config.get("raw_examples", []),
            parser_config.get("historical_examples", []),
        ):
            if name not in seen:
                fields.append({
                    "name": name,
                    "type": None,
                    "source": "raw_examples",
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

    def _extract_fields_from_examples(self, *example_groups: Any) -> List[str]:
        names = set()
        for group in example_groups:
            if not isinstance(group, list):
                continue
            for sample in group:
                if isinstance(sample, dict):
                    for k in sample.keys():
                        names.add(str(k))
                    if isinstance(sample.get("message"), str):
                        names.update(self._extract_kv_keys(sample["message"]))
                elif isinstance(sample, str):
                    text = sample.strip()
                    if not text:
                        continue
                    try:
                        parsed = json.loads(text)
                        if isinstance(parsed, dict):
                            for k in parsed.keys():
                                names.add(str(k))
                            if isinstance(parsed.get("message"), str):
                                names.update(self._extract_kv_keys(parsed["message"]))
                            continue
                    except Exception:
                        pass
                    names.update(re.findall(r'"([A-Za-z0-9_.-]+)"\s*:', text))
                    names.update(self._extract_kv_keys(text))
        return sorted(names)

    def _extract_kv_keys(self, text: str) -> List[str]:
        if not isinstance(text, str) or not text:
            return []
        keys = set()
        for key in re.findall(r'([A-Za-z0-9_.-]+)\s*=\s*"(?:[^"\\]|\\.)*"', text):
            keys.add(key)
        for key in re.findall(r'([A-Za-z0-9_.-]+)\s*=\s*[^"\s]+', text):
            keys.add(key)
        return sorted(keys)

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

        # Helper-based mappings common in generated scripts:
        # setNestedField(result, "field.path", value)
        for m in re.findall(r'setNestedField\s*\(\s*[^,]+,\s*["\']([^"\']+)["\']', lua_code):
            fields.add(m)

        # Bracket writes on result/output tables: result["field"] = ...
        for m in re.findall(r'(?:result|output)\s*\[\s*["\']([^"\']+)["\']\s*\]\s*=', lua_code):
            fields.add(m)

        return fields

    def _normalize(self, name: str) -> str:
        """Normalize a field name for fuzzy comparison."""
        return name.lower().replace(".", "_").replace("-", "_")
