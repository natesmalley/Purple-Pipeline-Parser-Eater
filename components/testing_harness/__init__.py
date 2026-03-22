"""
Testing Harness for Purple Pipeline Parser Eater

5-point confidence validation system:
1. Lua validity checking (syntax + structure)
2. Lua linting (best practices + quality score)
3. OCSF field mapping (multi-version schema validation)
4. Source parser field analysis (coverage tracking)
5. Test event execution (dual execution + field tracing)
"""

from .lua_validity_checker import LuaValidityChecker
from .lua_linter import LuaLinter
from .ocsf_schema_registry import OCSFSchemaRegistry
from .ocsf_field_analyzer import OCSFFieldAnalyzer
from .source_parser_analyzer import SourceParserAnalyzer
from .test_event_builder import TestEventBuilder
from .dual_execution_engine import DualExecutionEngine
from .jarvis_event_bridge import JarvisEventBridge
from .harness_orchestrator import HarnessOrchestrator

__all__ = [
    "LuaValidityChecker",
    "LuaLinter",
    "OCSFSchemaRegistry",
    "OCSFFieldAnalyzer",
    "SourceParserAnalyzer",
    "TestEventBuilder",
    "DualExecutionEngine",
    "JarvisEventBridge",
    "HarnessOrchestrator",
]
