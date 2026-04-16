"""Minimal Observo LUA template registry (Phase 3.G collapse).

The old 329-line module carried 6 legacy `function transform(event)` template
bodies that nothing actually consumed. The only live caller is
``orchestrator/core.py`` + ``orchestrator/phase3_generate_lua.py``, which reads
only ``template.name`` as a parser-type tag. Everything else was dead code.

This collapse preserves:
  - class name ``ObservoLuaTemplateRegistry``
  - method ``get_template_for_parser(parser_type, has_ocsf)`` returning an
    object with a ``.name`` attribute
  - module constant ``OBSERVO_TEMPLATE_REGISTRY`` for legacy imports
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class LuaTemplate:
    """Shim dataclass - only ``.name`` is read by live code."""
    name: str


# {parser_type: template_name}
_PARSER_TYPE_TO_TEMPLATE: Dict[str, str] = {
    "authentication": "ocsf_authentication_mapping",
    "network": "ocsf_network_mapping",
    "firewall": "ocsf_network_mapping",
    "edr": "ocsf_detection_finding",
    "alert": "ocsf_detection_finding",
    "dns": "ocsf_dns_activity",
    "http": "ocsf_http_activity",
    "file": "ocsf_file_activity",
    "process": "ocsf_process_activity",
    "unknown": "field_extraction_generic",
}


class ObservoLuaTemplateRegistry:
    """Registry shim - returns a LuaTemplate with only a ``.name`` tag."""

    def __init__(self) -> None:
        self.templates: Dict[str, LuaTemplate] = {
            name: LuaTemplate(name=name)
            for name in set(_PARSER_TYPE_TO_TEMPLATE.values())
        }
        # Also register a generic fallback used by get_template_for_parser
        fallback = "field_extraction_generic"
        self.templates.setdefault(fallback, LuaTemplate(name=fallback))

    def get_template(self, name: str) -> Optional[LuaTemplate]:
        return self.templates.get(name)

    def get_template_for_parser(
        self,
        parser_type: str,
        has_ocsf: bool = False,
    ) -> LuaTemplate:
        key = (parser_type or "").lower()
        tmpl_name = _PARSER_TYPE_TO_TEMPLATE.get(key, "field_extraction_generic")
        return self.templates.get(tmpl_name, LuaTemplate(name=tmpl_name))


OBSERVO_TEMPLATE_REGISTRY = ObservoLuaTemplateRegistry()


def get_observo_template(name: str) -> Optional[LuaTemplate]:
    return OBSERVO_TEMPLATE_REGISTRY.get_template(name)
