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
        try:
            from components.testing_harness.jarvis_event_bridge import JarvisEventBridge
            self._jarvis_bridge = JarvisEventBridge()
        except Exception:
            self._jarvis_bridge = None

    def _get_agent(self):
        """Lazy-init the agentic Lua generator."""
        if self._agent is None:
            import os
            from components.agentic_lua_generator import AgenticLuaGenerator

            anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")
            openai_api_key = os.environ.get("OPENAI_API_KEY")
            provider_preference = (os.environ.get("LLM_PROVIDER_PREFERENCE") or "openai").strip().lower()
            llm_max_tokens_raw = os.environ.get("LLM_MAX_TOKENS", "3000")
            llm_max_iterations_raw = os.environ.get("LLM_MAX_ITERATIONS", "2")
            try:
                llm_max_tokens = max(256, min(int(llm_max_tokens_raw), 8192))
            except (TypeError, ValueError):
                llm_max_tokens = 3000
            try:
                llm_max_iterations = max(1, min(int(llm_max_iterations_raw), 5))
            except (TypeError, ValueError):
                llm_max_iterations = 2

            def _build_anthropic():
                anthropic_model = os.environ.get("ANTHROPIC_MODEL", "claude-3-haiku-20240307")
                return AgenticLuaGenerator(
                    api_key=anthropic_api_key,
                    model=anthropic_model,
                    provider="anthropic",
                    max_output_tokens=llm_max_tokens,
                    max_iterations=llm_max_iterations,
                )

            def _build_openai():
                openai_model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
                return AgenticLuaGenerator(
                    api_key=openai_api_key,
                    model=openai_model,
                    provider="openai",
                    max_output_tokens=llm_max_tokens,
                    max_iterations=llm_max_iterations,
                )

            def _build_gemini():
                gemini_api_key = os.environ.get("GEMINI_API_KEY")
                gemini_model = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")
                return AgenticLuaGenerator(
                    api_key=gemini_api_key,
                    model=gemini_model,
                    provider="gemini",
                    max_output_tokens=llm_max_tokens,
                    max_iterations=llm_max_iterations,
                )

            if provider_preference == "anthropic":
                if anthropic_api_key:
                    self._agent = _build_anthropic()
                elif openai_api_key:
                    self._agent = _build_openai()
            elif provider_preference == "openai":
                if openai_api_key:
                    self._agent = _build_openai()
                elif anthropic_api_key:
                    self._agent = _build_anthropic()
            elif provider_preference == "gemini":
                gemini_api_key = os.environ.get("GEMINI_API_KEY")
                if gemini_api_key:
                    self._agent = _build_gemini()
                elif anthropic_api_key:
                    self._agent = _build_anthropic()
                elif openai_api_key:
                    self._agent = _build_openai()
            else:
                raise ValueError(
                    "Unknown LLM provider preference: %r. "
                    "Supported: anthropic, openai, gemini"
                    % provider_preference
                )
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

    def list_parser_names(self) -> List[str]:
        return [row["parser_name"] for row in self.list_parsers()]

    def _find_entry(self, parser_name: str) -> Optional[Dict[str, Any]]:
        for entry in self._load_converted():
            if entry.get("parser_name") == parser_name:
                return entry
        return None

    def _example_log(self, entry: Dict[str, Any]) -> str:
        return self._example_log_with_provenance(entry)["example_log"]

    def _example_log_with_provenance(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        parser_name = str(entry.get("parser_name", "unknown"))
        mode = str(entry.get("ingestion_mode", "unknown"))
        parser_slug = normalize_name(parser_name)
        tokens = parser_slug.split("_")
        vendor = tokens[0] if tokens else "vendor"
        product = "_".join(tokens[1:3]) if len(tokens) > 1 else "product"
        strategy = self.get_event_generation_strategy(parser_name)

        if self._jarvis_bridge and self._jarvis_bridge.available:
            jarvis_events = self._jarvis_bridge.get_events(parser_name, count=1)
            if jarvis_events:
                event_data = jarvis_events[0].get("event")
                if isinstance(event_data, dict):
                    return {
                        "example_log": json.dumps(event_data, indent=2),
                        "sample_provenance": {
                            **strategy,
                            "example_format": "jarvis_json",
                        },
                    }
                if isinstance(event_data, str):
                    return {
                        "example_log": event_data,
                        "sample_provenance": {
                            **strategy,
                            "example_format": "jarvis_raw",
                        },
                    }

        if "cloudwatch" in parser_slug:
            payload = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "parser": parser_name,
                "awsRegion": "us-east-1",
                "logGroup": "/aws/lambda/example-function",
                "logStream": "2026/03/22/[$LATEST]f4c1a3d1b2c34f6a8d9e0f1a2b3c4d5e",
                "eventSource": "lambda.amazonaws.com",
                "eventName": "Invoke",
                "sourceIPAddress": "52.95.12.34",
                "userIdentity": {
                    "type": "IAMUser",
                    "arn": "arn:aws:iam::123456789012:user/alice",
                    "userName": "alice",
                },
                "requestParameters": {"functionName": "example-function"},
                "responseElements": {"statusCode": 200},
                "message": "Lambda invocation completed successfully",
            }
            return {
                "example_log": json.dumps(payload, indent=2),
                "sample_provenance": {
                    **strategy,
                    "source": "fallback",
                    "example_format": "fallback_json",
                },
            }

        if "cloudflare" in parser_slug and "waf" in parser_slug:
            payload = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "parser": parser_name,
                "vendor": "cloudflare",
                "product": "waf",
                "zone": "example.com",
                "ray_id": "7f9a3b4c5d6e7f80",
                "client_ip": "203.0.113.42",
                "client_country": "US",
                "http_method": "GET",
                "http_host": "api.example.com",
                "http_path": "/login",
                "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4)",
                "waf_action": "block",
                "waf_rule_id": "100173",
                "waf_rule_message": "SQL injection pattern detected",
                "edge_response_status": 403,
                "message": "Cloudflare WAF blocked suspicious request",
            }
            return {
                "example_log": json.dumps(payload, indent=2),
                "sample_provenance": {
                    **strategy,
                    "source": "fallback",
                    "example_format": "fallback_json",
                },
            }

        if mode == "syslog":
            now = datetime.utcnow().strftime("%b %d %H:%M:%S")
            return {
                "example_log": (
                f"<134>{now} {vendor}-gateway {product}[1234]: "
                f"parser={parser_name} action=allow src=10.10.10.5 dst=192.168.1.10 "
                f"proto=tcp dpt=443 msg=sample_event"
                ),
                "sample_provenance": {
                    **strategy,
                    "source": "fallback",
                    "example_format": "fallback_syslog",
                },
            }

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
        return {
            "example_log": json.dumps(payload, indent=2),
            "sample_provenance": {
                **strategy,
                "source": "fallback",
                "example_format": "fallback_json",
            },
        }

    def build_parser(self, parser_name: str) -> Optional[Dict[str, Any]]:
        entry = self._find_entry(parser_name)
        if not entry:
            return None

        lua_data = build_lua_content(entry)
        parser_slug = normalize_name(parser_name) or "unknown"
        self.lua_dir.mkdir(parents=True, exist_ok=True)
        lua_path = self.lua_dir / f"{parser_slug}.lua"
        lua_path.write_text(lua_data["content"], encoding="utf-8")

        example = self._example_log_with_provenance(entry)
        return {
            "parser_name": parser_name,
            "ingestion_mode": entry.get("ingestion_mode"),
            "processing_template_used": entry.get("processing_template_used"),
            "generated_source": lua_data["source_kind"],
            "lua_file": str(lua_path),
            "lua_code": lua_data["content"],
            "example_log": example["example_log"],
            "sample_provenance": example["sample_provenance"],
        }

    def build_parser_with_agent(
        self,
        parser_name: str,
        force_regenerate: bool = False,
        target_parser_name: Optional[str] = None,
        raw_examples: Optional[List[Any]] = None,
        context_examples: Optional[List[Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Generate Lua via the agentic LLM workflow with harness feedback loop."""
        entry = self._find_entry(parser_name)
        if not entry:
            return None
        entry_for_generation = dict(entry)
        effective_parser_name = target_parser_name or parser_name
        entry_for_generation["parser_name"] = effective_parser_name
        if raw_examples:
            entry_for_generation["raw_examples"] = raw_examples
        if context_examples:
            entry_for_generation["historical_examples"] = context_examples

        agent = self._get_agent()
        if not agent:
            return {"error": "No LLM API key set (ANTHROPIC_API_KEY or OPENAI_API_KEY) - agent generation unavailable"}

        result = agent.generate(entry_for_generation, force_regenerate=force_regenerate)

        if result.get("error"):
            return result

        # Write the Lua file
        parser_slug = normalize_name(effective_parser_name) or "unknown"
        self.lua_dir.mkdir(parents=True, exist_ok=True)
        lua_path = self.lua_dir / f"{parser_slug}.lua"
        lua_path.write_text(result["lua_code"], encoding="utf-8")

        example = self._example_log_with_provenance(entry)
        return {
            "parser_name": effective_parser_name,
            "source_parser_name": parser_name,
            "ingestion_mode": result.get("ingestion_mode"),
            "processing_template_used": None,
            "generated_source": "agent_generated",
            "lua_file": str(lua_path),
            "lua_code": result["lua_code"],
            "example_log": example["example_log"],
            "sample_provenance": example["sample_provenance"],
            "confidence_score": result.get("confidence_score"),
            "confidence_grade": result.get("confidence_grade"),
            "iterations": result.get("iterations"),
            "ocsf_class": result.get("ocsf_class_name"),
            "quality": result.get("quality"),
            "examples_used": result.get("examples_used"),
            "harness_report": result.get("harness_report"),
        }

    def get_event_generation_strategy(self, parser_name: str) -> Dict[str, Any]:
        if not self._jarvis_bridge:
            return {
                "source": "fallback",
                "jarvis_available": False,
                "jarvis_match_type": "none",
                "jarvis_generator_key": "",
            }
        if hasattr(self._jarvis_bridge, "resolve_generator"):
            resolved = self._jarvis_bridge.resolve_generator(parser_name)
        else:
            has_gen = False
            if hasattr(self._jarvis_bridge, "has_generator"):
                has_gen = bool(self._jarvis_bridge.has_generator(parser_name))
            resolved = {
                "match_type": "exact" if has_gen else "none",
                "generator_key": parser_name if has_gen else "",
            }
        source = "jarvis" if resolved.get("match_type") != "none" else "fallback"
        return {
            "source": source,
            "jarvis_available": bool(getattr(self._jarvis_bridge, "available", False)),
            "jarvis_match_type": resolved.get("match_type", "none"),
            "jarvis_generator_key": resolved.get("generator_key", ""),
        }

    def build_from_raw_examples(
        self,
        parser_name: str,
        raw_examples: List[Any],
        context_examples: Optional[List[Any]] = None,
        force_regenerate: bool = False,
    ) -> Dict[str, Any]:
        """
        Generate Lua from raw examples using the same agentic path.

        This supports net-new parser onboarding where parser metadata is limited.
        """
        agent = self._get_agent()
        if not agent:
            return {"error": "No LLM API key set (ANTHROPIC_API_KEY or OPENAI_API_KEY) - agent generation unavailable"}

        synthetic_entry: Dict[str, Any] = {
            "parser_name": parser_name,
            "ingestion_mode": "push",
            "raw_examples": raw_examples,
            "historical_examples": context_examples or [],
            "config": {"parser_name": parser_name},
        }
        result = agent.generate(synthetic_entry, force_regenerate=force_regenerate)
        if result.get("error"):
            return result

        parser_slug = normalize_name(parser_name) or "unknown"
        self.lua_dir.mkdir(parents=True, exist_ok=True)
        lua_path = self.lua_dir / f"{parser_slug}.lua"
        lua_path.write_text(result["lua_code"], encoding="utf-8")

        first_example = raw_examples[0] if raw_examples else {}
        if isinstance(first_example, str):
            example_log = first_example
        else:
            example_log = json.dumps(first_example, indent=2)

        return {
            "parser_name": parser_name,
            "ingestion_mode": result.get("ingestion_mode", "push"),
            "processing_template_used": None,
            "generated_source": "agent_generated_raw_examples",
            "lua_file": str(lua_path),
            "lua_code": result["lua_code"],
            "example_log": example_log,
            "sample_provenance": {
                "source": "user_raw_examples",
                "jarvis_available": bool(getattr(self._jarvis_bridge, "available", False)),
                "jarvis_match_type": "none",
                "jarvis_generator_key": "",
                "example_format": "user_supplied",
            },
            "confidence_score": result.get("confidence_score"),
            "confidence_grade": result.get("confidence_grade"),
            "iterations": result.get("iterations"),
            "ocsf_class": result.get("ocsf_class_name"),
            "quality": result.get("quality"),
            "examples_used": result.get("examples_used"),
            "harness_report": result.get("harness_report"),
            "raw_examples_count": len(raw_examples),
        }
