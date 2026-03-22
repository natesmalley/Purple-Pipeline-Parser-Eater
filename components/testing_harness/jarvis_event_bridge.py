"""Jarvis Event Bridge - loads realistic vendor events from Jarvis event generators.

Maps parser names to Jarvis generator modules and returns events in harness format.
Falls through gracefully when Jarvis is not available.
"""

import importlib
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

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
            Path("../jarvis_coding/Backend/event_generators"),
            Path.home() / "jarvis_coding" / "Backend" / "event_generators",
        ]
        for p in candidates:
            if p.exists():
                return p.resolve()
        return None

    def has_generator(self, parser_name: str) -> bool:
        """Check if a Jarvis generator exists for this parser."""
        if not self._available:
            return False
        normalized = self._normalize_parser_name(parser_name)
        return normalized in PARSER_TO_JARVIS

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

        normalized = self._normalize_parser_name(parser_name)
        mapping = PARSER_TO_JARVIS.get(normalized)
        if not mapping:
            return []

        try:
            events = self._load_events(mapping, count)
            return self._wrap_events(events, parser_name)
        except Exception as e:
            logger.warning("Failed to load Jarvis events for %s: %s", parser_name, e)
            return []

    def _normalize_parser_name(self, name: str) -> str:
        """Normalize parser name for lookup."""
        return name.lower().replace("-", "_").replace(" ", "_").split("-latest")[0]

    def _load_events(self, mapping: Dict[str, str], count: int) -> List[Any]:
        """Dynamically import and call a Jarvis generator."""
        module_path = f"event_generators.{mapping['module']}"
        func_name = mapping["func"]

        mod = importlib.import_module(module_path)
        gen_func = getattr(mod, func_name)

        events = []
        for _ in range(count):
            evt = gen_func()
            if evt is not None:
                events.append(evt)
        return events

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
        return sorted(PARSER_TO_JARVIS.keys())
