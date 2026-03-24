"""Jarvis Event Bridge - loads realistic vendor events from Jarvis event generators.

Maps parser names to Jarvis generator modules and returns events in harness format.
Falls through gracefully when Jarvis is not available.
"""

import importlib
import logging
import sys
import types
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Map parser names to Jarvis event generator module paths
# Format: parser_name -> (category/module_name, generator_function)
PARSER_TO_JARVIS: Dict[str, Dict[str, str]] = {
    # Authentication / IAM
    "okta_authentication": {"module": "iam.okta_events", "func": "generate_event"},
    "okta_system_log": {"module": "iam.okta_events", "func": "generate_event"},
    "cisco_duo": {"module": "iam.duo_events", "func": "generate_event"},
    "azure_ad": {"module": "iam.azure_ad_events", "func": "generate_event"},
    "cyberark": {"module": "iam.cyberark_events", "func": "generate_event"},
    "ping_identity": {"module": "iam.ping_events", "func": "generate_event"},

    # Network / Firewall
    "cisco_asa": {"module": "network.cisco_asa_events", "func": "generate_event"},
    "palo_alto": {"module": "network.paloalto_events", "func": "generate_event"},
    "palo_alto_firewall": {"module": "network.paloalto_events", "func": "generate_event"},
    "fortinet_fortigate": {"module": "network.fortigate_events", "func": "generate_event"},
    "checkpoint": {"module": "network.checkpoint_events", "func": "generate_event"},
    "barracuda_firewall": {"module": "network.barracuda_events", "func": "generate_event"},
    "juniper_srx": {"module": "network.juniper_events", "func": "generate_event"},
    "sonicwall": {"module": "network.sonicwall_events", "func": "generate_event"},
    "meraki": {"module": "network.meraki_events", "func": "generate_event"},

    # Cloud
    "aws_cloudtrail": {"module": "cloud.cloudtrail_events", "func": "generate_event"},
    "aws_guardduty": {"module": "cloud.guardduty_events", "func": "generate_event"},
    "aws_vpc_flow": {"module": "cloud.vpc_flow_events", "func": "generate_event"},
    "azure_activity": {"module": "cloud.azure_activity_events", "func": "generate_event"},
    "gcp_audit": {"module": "cloud.gcp_audit_events", "func": "generate_event"},

    # EDR / Detection
    "crowdstrike": {"module": "edr.crowdstrike_events", "func": "generate_event"},
    "sentinelone": {"module": "edr.sentinelone_events", "func": "generate_event"},
    "microsoft_defender": {"module": "edr.defender_events", "func": "generate_event"},
    "carbon_black": {"module": "edr.carbonblack_events", "func": "generate_event"},

    # Web / Proxy
    "nginx": {"module": "web.nginx_events", "func": "generate_event"},
    "apache_http": {"module": "web.apache_events", "func": "generate_event"},
    "cloudflare": {"module": "web.cloudflare_events", "func": "generate_event"},
    "squid": {"module": "web.squid_events", "func": "generate_event"},

    # DNS
    "dns_bind": {"module": "dns.bind_events", "func": "generate_event"},
    "infoblox": {"module": "dns.infoblox_events", "func": "generate_event"},

    # Endpoint
    "windows_security": {"module": "endpoint.windows_security_events", "func": "generate_event"},
    "linux_syslog": {"module": "endpoint.linux_syslog_events", "func": "generate_event"},
    "sysmon": {"module": "endpoint.sysmon_events", "func": "generate_event"},
}


class JarvisEventBridge:
    """Bridge between Jarvis event generators and the testing harness."""

    def __init__(self, jarvis_root: Optional[Path] = None):
        """
        Initialize the bridge.

        Args:
            jarvis_root: Path to jarvis_coding/Backend/event_generators/.
                         If None, searches common locations.
        """
        self.jarvis_root = self._find_jarvis_root(jarvis_root)
        self._available = self.jarvis_root is not None and self.jarvis_root.exists()
        self._dynamic_generators: Dict[str, str] = {}
        self._module_prefix = "event_generators"
        if self.jarvis_root is not None:
            self._module_prefix = self.jarvis_root.name
            self._dynamic_generators = self._discover_generators(self.jarvis_root)
        if self._available:
            # Add to sys.path so we can import generators
            parent = str(self.jarvis_root.parent)
            if parent not in sys.path:
                sys.path.insert(0, parent)
            logger.info("Jarvis event bridge initialized: %s", self.jarvis_root)
        else:
            logger.info("Jarvis event generators not found — bridge disabled")

    @property
    def available(self) -> bool:
        return self._available

    def _find_jarvis_root(self, explicit: Optional[Path]) -> Optional[Path]:
        if explicit and explicit.exists():
            return explicit

        candidates = [
            Path("jarvis_coding/Backend/event_generators"),
            Path("docs/reference/jarvis_event_generators"),
            Path("../jarvis_coding/Backend/event_generators"),
            Path.home() / "jarvis_coding" / "Backend" / "event_generators",
        ]
        for p in candidates:
            if p.exists():
                return p.resolve()
        return None

    def _discover_generators(self, jarvis_root: Path) -> Dict[str, str]:
        generators: Dict[str, str] = {}
        for path in sorted(jarvis_root.rglob("*.py")):
            if path.name.startswith("_"):
                continue
            if "shared" in path.parts:
                continue
            rel = path.relative_to(jarvis_root).with_suffix("")
            parser_key = self._normalize_parser_name(path.stem)
            module_path = ".".join(rel.parts)
            generators[parser_key] = module_path
        return generators

    def has_generator(self, parser_name: str) -> bool:
        """Check if a Jarvis generator exists for this parser."""
        if not self._available:
            return False
        resolved = self.resolve_generator(parser_name)
        return resolved["match_type"] != "none"

    def get_events(self, parser_name: str, count: int = 4) -> List[Dict[str, Any]]:
        """
        Get realistic test events from Jarvis for a parser.

        Args:
            parser_name: Parser name to get events for
            count: Number of events to generate

        Returns:
            List of events in harness format:
            [{"name": str, "event": dict/str, "expected_behavior": str}]
        """
        if not self._available:
            return []

        resolved = self.resolve_generator(parser_name)
        if resolved["match_type"] == "none":
            return []

        try:
            if resolved["source"] == "static":
                mapping = PARSER_TO_JARVIS[resolved["generator_key"]]
                events = self._load_events(mapping, count)
            else:
                events = self._load_dynamic_events(
                    resolved["module_path"], resolved["generator_key"], count
                )
            return self._wrap_events(events, parser_name)
        except Exception as e:
            logger.warning("Failed to load Jarvis events for %s: %s", parser_name, e)
            return []

    def resolve_generator(self, parser_name: str) -> Dict[str, str]:
        """
        Resolve parser -> generator mapping using exact, then alias matching.

        Returns:
            {
                "match_type": "exact" | "alias" | "none",
                "source": "static" | "dynamic" | "",
                "generator_key": str,
                "module_path": str,
            }
        """
        normalized = self._normalize_parser_name(parser_name)

        if normalized in PARSER_TO_JARVIS:
            return {
                "match_type": "exact",
                "source": "static",
                "generator_key": normalized,
                "module_path": PARSER_TO_JARVIS[normalized]["module"],
            }
        if normalized in self._dynamic_generators:
            return {
                "match_type": "exact",
                "source": "dynamic",
                "generator_key": normalized,
                "module_path": self._dynamic_generators[normalized],
            }

        key, source = self._best_alias_match(normalized)
        if not key:
            return {
                "match_type": "none",
                "source": "",
                "generator_key": "",
                "module_path": "",
            }

        if source == "static":
            module_path = PARSER_TO_JARVIS[key]["module"]
        else:
            module_path = self._dynamic_generators[key]
        return {
            "match_type": "alias",
            "source": source,
            "generator_key": key,
            "module_path": module_path,
        }

    def _best_alias_match(self, normalized: str) -> Tuple[str, str]:
        parser_tokens = {t for t in normalized.split("_") if t}
        if not parser_tokens:
            return "", ""

        best_score = 0.0
        best_key = ""
        best_source = ""

        for key in PARSER_TO_JARVIS:
            score = self._token_score(parser_tokens, key)
            if score > best_score:
                best_score = score
                best_key = key
                best_source = "static"

        for key in self._dynamic_generators:
            score = self._token_score(parser_tokens, key)
            if score > best_score:
                best_score = score
                best_key = key
                best_source = "dynamic"

        if best_score < 0.5:
            return "", ""
        return best_key, best_source

    def _token_score(self, parser_tokens: set, candidate_key: str) -> float:
        cand_tokens = {t for t in candidate_key.split("_") if t}
        if not cand_tokens:
            return 0.0
        inter = len(parser_tokens & cand_tokens)
        union = len(parser_tokens | cand_tokens)
        if inter == 0 or union == 0:
            return 0.0
        score = inter / union
        if candidate_key in "_".join(sorted(parser_tokens)):
            score += 0.1
        return min(score, 1.0)

    def _normalize_parser_name(self, name: str) -> str:
        """Normalize parser name for lookup."""
        normalized = name.lower().replace("-", "_").replace(" ", "_")
        suffixes = (
            "_latest",
            "_lastest",
            "_logs",
            "_log",
            "_collector",
            "_events",
        )
        changed = True
        while changed:
            changed = False
            for suffix in suffixes:
                if normalized.endswith(suffix):
                    normalized = normalized[: -len(suffix)]
                    changed = True
        return normalized.strip("_")

    def _load_events(self, mapping: Dict[str, str], count: int) -> List[Any]:
        """Dynamically import and call a Jarvis generator."""
        module_path = f"{self._module_prefix}.{mapping['module']}"
        func_name = mapping["func"]

        mod = importlib.import_module(module_path)
        gen_func = getattr(mod, func_name)

        events = []
        for _ in range(count):
            evt = gen_func()
            if evt is not None:
                events.append(evt)
        return events

    def _load_dynamic_events(self, module_path: str, key: str, count: int) -> List[Any]:
        mod = self._import_dynamic_module(module_path)

        candidate_names = [
            "generate_event",
            "generate",
            f"{key}_log",
            f"{key}_event",
        ]
        for name in list(candidate_names):
            alt = name.replace("__", "_")
            if alt not in candidate_names:
                candidate_names.append(alt)

        callable_fn = None
        for name in candidate_names:
            if hasattr(mod, name) and callable(getattr(mod, name)):
                callable_fn = getattr(mod, name)
                break

        if callable_fn is None:
            for attr in sorted(dir(mod)):
                if attr.startswith("_"):
                    continue
                if not (attr.endswith("_log") or attr.endswith("_event")):
                    continue
                fn = getattr(mod, attr)
                if callable(fn):
                    callable_fn = fn
                    break

        if callable_fn is None:
            raise RuntimeError(f"No callable generator function found in module {module_path}")

        events: List[Any] = []
        for _ in range(count):
            evt = callable_fn()
            if evt is not None:
                events.append(evt)
        return events

    def _import_dynamic_module(self, module_path: str):
        full_module_path = f"{self._module_prefix}.{module_path}"
        try:
            return importlib.import_module(full_module_path)
        except TypeError as exc:
            # Python 3.9 compatibility for generators authored with PEP 604
            # style annotations (`dict | None`).
            if "unsupported operand type(s) for |" not in str(exc):
                raise
            if self.jarvis_root is None:
                raise

            file_path = self.jarvis_root / Path(*module_path.split(".")).with_suffix(".py")
            if not file_path.exists():
                raise

            source = file_path.read_text(encoding="utf-8", errors="replace")
            compat_source = "from __future__ import annotations\n" + source
            mod = types.ModuleType(full_module_path)
            mod.__file__ = str(file_path)
            mod.__package__ = full_module_path.rsplit(".", 1)[0]
            exec(compile(compat_source, str(file_path), "exec"), mod.__dict__)
            return mod

    def _wrap_events(self, raw_events: List[Any], parser_name: str) -> List[Dict[str, Any]]:
        """Wrap raw events into harness test event format."""
        wrapped = []
        scenarios = ["happy_path", "normal_event", "variant_event", "edge_case"]

        for i, raw in enumerate(raw_events):
            scenario = scenarios[i] if i < len(scenarios) else f"event_{i}"

            # Handle different formats
            if isinstance(raw, dict):
                event_data = raw
            elif isinstance(raw, str):
                # Syslog string — wrap as log field
                event_data = {"log": raw, "message": raw}
            elif isinstance(raw, (list, tuple)):
                # CSV or multi-value — convert to dict
                event_data = {"fields": list(raw), "raw": str(raw)}
            else:
                event_data = {"raw": str(raw)}

            wrapped.append({
                "name": f"jarvis_{parser_name}_{scenario}",
                "event": event_data,
                "expected_behavior": f"Should map {parser_name} event to OCSF format",
                "source": "jarvis",
            })

        return wrapped

    def list_available_parsers(self) -> List[str]:
        """List parser names that have Jarvis generators."""
        if not self._available:
            return []
        all_keys = set(PARSER_TO_JARVIS.keys()) | set(self._dynamic_generators.keys())
        return sorted(all_keys)
