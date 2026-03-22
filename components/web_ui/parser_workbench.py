"""Parser Lua workbench utilities for the web UI."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from components.ai_siem_pipeline_converter import normalize_name
from components.lua_exporter import build_lua_content


class ParserLuaWorkbench:
    """Loads parser conversion output and builds Lua previews on demand."""

    def __init__(self, repo_root: Optional[Path] = None):
        self.repo_root = repo_root or Path.cwd()
        self.converted_path = self.repo_root / "output" / "ai_siem_parser_source_components.json"
        self.lua_dir = self.repo_root / "output" / "parser_lua_serializers"
        self.lua_dir.mkdir(parents=True, exist_ok=True)
        self._agent = None

    def _get_agent(self):
        """Lazy-init the agentic Lua generator."""
        if self._agent is None:
            import os
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if api_key:
                from components.agentic_lua_generator import AgenticLuaGenerator
                self._agent = AgenticLuaGenerator(api_key=api_key)
        return self._agent

    def _load_converted(self) -> List[Dict[str, Any]]:
        if not self.converted_path.exists():
            return []
        try:
            data = json.loads(self.converted_path.read_text(encoding="utf-8"))
        except Exception:
            return []
        converted = data.get("converted", []) if isinstance(data, dict) else []
        return converted if isinstance(converted, list) else []

    def list_parsers(self) -> List[Dict[str, Any]]:
        rows = []
        for entry in self._load_converted():
            parser_name = entry.get("parser_name")
            if not isinstance(parser_name, str):
                continue
            rows.append(
                {
                    "parser_name": parser_name,
                    "ingestion_mode": entry.get("ingestion_mode"),
                    "processing_template_used": entry.get("processing_template_used"),
                    "matched_pipeline_template": entry.get("matched_pipeline_template"),
                }
            )
        rows.sort(key=lambda x: x["parser_name"])
        return rows

    def _find_entry(self, parser_name: str) -> Optional[Dict[str, Any]]:
        for entry in self._load_converted():
            if entry.get("parser_name") == parser_name:
                return entry
        return None

    def _example_log(self, entry: Dict[str, Any]) -> str:
        parser_name = str(entry.get("parser_name", "unknown"))
        mode = str(entry.get("ingestion_mode", "unknown"))
        tokens = normalize_name(parser_name).split("_")
        vendor = tokens[0] if tokens else "vendor"
        product = "_".join(tokens[1:3]) if len(tokens) > 1 else "product"

        if mode == "syslog":
            now = datetime.utcnow().strftime("%b %d %H:%M:%S")
            return (
                f"<134>{now} {vendor}-gateway {product}[1234]: "
                f"parser={parser_name} action=allow src=10.10.10.5 dst=192.168.1.10 "
                f"proto=tcp dpt=443 msg=sample_event"
            )

        payload = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "vendor": vendor,
            "product": product,
            "parser": parser_name,
            "event_type": "sample_event",
            "result": "success",
            "message": f"Sample event for {parser_name}",
            "user": {"name": "alice@example.com", "id": "u-1001"},
            "src": {"ip": "10.10.10.5", "hostname": f"{vendor}-collector"},
            "dst": {"ip": "192.168.1.10", "hostname": "target-host"},
        }
        return json.dumps(payload, indent=2)

    def build_parser(self, parser_name: str) -> Optional[Dict[str, Any]]:
        entry = self._find_entry(parser_name)
        if not entry:
            return None

        lua_data = build_lua_content(entry)
        parser_slug = normalize_name(parser_name) or "unknown"
        lua_path = self.lua_dir / f"{parser_slug}.lua"
        lua_path.write_text(lua_data["content"], encoding="utf-8")

        return {
            "parser_name": parser_name,
            "ingestion_mode": entry.get("ingestion_mode"),
            "processing_template_used": entry.get("processing_template_used"),
            "generated_source": lua_data["source_kind"],
            "lua_file": str(lua_path),
            "lua_code": lua_data["content"],
            "example_log": self._example_log(entry),
        }

    def build_parser_with_agent(
        self, parser_name: str, force_regenerate: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Generate Lua via the agentic LLM workflow with harness feedback loop."""
        entry = self._find_entry(parser_name)
        if not entry:
            return None

        agent = self._get_agent()
        if not agent:
            return {"error": "ANTHROPIC_API_KEY not set - agent generation unavailable"}

        result = agent.generate(entry, force_regenerate=force_regenerate)

        if result.get("error"):
            return result

        # Write the Lua file
        parser_slug = normalize_name(parser_name) or "unknown"
        lua_path = self.lua_dir / f"{parser_slug}.lua"
        lua_path.write_text(result["lua_code"], encoding="utf-8")

        return {
            "parser_name": parser_name,
            "ingestion_mode": result.get("ingestion_mode"),
            "processing_template_used": None,
            "generated_source": "agent_generated",
            "lua_file": str(lua_path),
            "lua_code": result["lua_code"],
            "example_log": self._example_log(entry),
            "confidence_score": result.get("confidence_score"),
            "confidence_grade": result.get("confidence_grade"),
            "iterations": result.get("iterations"),
            "ocsf_class": result.get("ocsf_class_name"),
            "quality": result.get("quality"),
            "examples_used": result.get("examples_used"),
            "harness_report": result.get("harness_report"),
        }
