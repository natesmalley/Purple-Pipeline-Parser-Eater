# Agent Task 2: Refactor orchestrator.py into Phase-Based Modules

**Agent Model:** Claude Haiku (fast, efficient)
**Estimated Time:** 120 minutes
**Risk Level:** MEDIUM-HIGH (core workflow component)
**Files Modified:** 1 large file → 9 modular files

---

## Mission Objective

Refactor `orchestrator.py` (830 lines) into smaller, focused modules organized in `orchestrator/` directory, with each conversion phase isolated into its own module while maintaining 100% backward compatibility.

**Success Criteria:**
- [ ] Original file reduced to <100 lines (backward compatibility wrapper)
- [ ] 8-9 new focused modules created (~100-150 lines each)
- [ ] All 5 conversion phases working independently
- [ ] main.py still works without changes
- [ ] continuous_conversion_service.py still works
- [ ] All imports resolve correctly
- [ ] Zero syntax errors
- [ ] Zero functional regressions

---

## Current File Analysis

**File:** `orchestrator.py`
**Lines:** 830
**Main Class:** `ConversionSystemOrchestrator`

**File Structure:**
```
Lines   1-36:  Imports and dependencies
Lines  38-82:  Class definition and __init__
Lines  83-156: Config loading and env var expansion
Lines 157-196: Component initialization
Lines 197-237: Main workflow (run_complete_conversion)
Lines 238-321: Utility functions (hash, metadata)
Lines 322-361: Phase 1 - Parser scanning
Lines 362-407: Phase 2 - Parser analysis
Lines 408-476: Phase 3 - Lua generation
Lines 477-638: Phase 4 - Deployment and GitHub upload
Lines 639-660: Phase 5 - Report generation
Lines 661-761: Report generation (detailed)
Lines 762-776: JSON saving
Lines 777-791: Statistics saving
Lines 792-808: Display statistics
Lines 809-818: Cleanup
Lines 819-830: Main function
```

**Key Methods:**
- `__init__()` - Initialize with config
- `_load_config()` - Load and parse YAML config
- `_expand_environment_variables()` - Env var expansion
- `initialize_components()` - Setup all components
- `run_complete_conversion()` - Main workflow orchestrator
- `_phase_1_scan_parsers()` - Scan S1 parsers from GitHub
- `_phase_2_analyze_parsers()` - Claude AI analysis
- `_phase_3_generate_lua()` - Generate Lua code
- `_phase_4_deploy_and_upload()` - Deploy to Observo, upload to GitHub
- `_phase_5_generate_report()` - Create comprehensive report
- `_generate_comprehensive_report()` - Detailed report generation
- 8 utility methods for hashing, metadata, stats, cleanup

---

## Target Architecture

Create this directory structure:

```
orchestrator/
├── __init__.py          # Public interface (backward compatibility)
├── core.py              # Main orchestrator class (~150 lines)
├── config.py            # Configuration loading (~120 lines)
├── initializer.py       # Component initialization (~100 lines)
├── phase_1_scanner.py   # Phase 1: Parser scanning (~80 lines)
├── phase_2_analyzer.py  # Phase 2: Parser analysis (~100 lines)
├── phase_3_generator.py # Phase 3: Lua generation (~120 lines)
├── phase_4_deployer.py  # Phase 4: Deployment (~180 lines)
├── phase_5_reporter.py  # Phase 5: Report generation (~150 lines)
└── utils.py             # Utility functions (~100 lines)
```

---

## Step-by-Step Execution Plan

### STEP 1: Create Directory and __init__.py

**Action:**
```bash
mkdir -p orchestrator
```

**Create:** `orchestrator/__init__.py`
```python
"""
Orchestrator module for Purple Pipeline Parser Eater.

Coordinates the complete conversion workflow from scanning to deployment.
Refactored from orchestrator.py for better maintainability and testability.
"""

from .core import ConversionSystemOrchestrator

__all__ = ['ConversionSystemOrchestrator']
```

---

### STEP 2: Extract Utilities (utils.py)

**Create:** `orchestrator/utils.py`

**Content to Extract:**
- Lines 238-241: `_hash_string` static method
- Lines 241-321: `_build_manifest_metadata` static method
- Lines 762-776: `_save_json` method
- Lines 777-791: `_save_statistics` method
- Lines 792-808: `_display_final_statistics` method

**Code:**
```python
"""Utility functions for orchestrator operations."""

import hashlib
import json
import logging
from datetime import datetime, date
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)


def hash_string(value: str) -> str:
    """Generate SHA256 hash of a string."""
    return hashlib.sha256(value.encode()).hexdigest()


def build_manifest_metadata(
    parser_name: str,
    parser_type: str,
    parser_hash: str,
    lua_code: str,
    semantic_version: str,
    semantic_description: str,
    original_parser_content: str,
    analysis_result: Dict,
    generation_metadata: Dict,
    validation_result: Dict,
    ai_siem_metadata: Dict
) -> Dict:
    """
    Build comprehensive manifest metadata for parser.

    DIRECTOR REQUIREMENTS:
    - Requirement 1: Semantic versioning
    - Requirement 3: Comprehensive manifest with all metadata
    - Requirement 6: AI-SIEM classification metadata
    """
    # [COPY ENTIRE METHOD IMPLEMENTATION FROM orchestrator.py:241-321]
    pass  # Replace with full implementation


def save_json(data: Any, filepath: str) -> None:
    """
    Save data as JSON file with proper serialization.

    Args:
        data: Data to save
        filepath: Path to save file
    """
    def json_serial(obj):
        """JSON serializer for objects not serializable by default json code"""
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        raise TypeError(f"Type {type(obj)} not serializable")

    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=json_serial, ensure_ascii=False)
        logger.debug(f"Saved JSON to {filepath}")
    except Exception as e:
        logger.error(f"Failed to save JSON to {filepath}: {e}")
        raise


def save_statistics(stats: Dict, output_dir: Path) -> None:
    """
    Save conversion statistics to JSON file.

    Args:
        stats: Statistics dictionary
        output_dir: Output directory path
    """
    # [COPY IMPLEMENTATION FROM orchestrator.py:777-791]
    pass  # Replace with full implementation


def display_final_statistics(stats: Dict) -> None:
    """
    Display final statistics summary.

    Args:
        stats: Statistics dictionary
    """
    # [COPY IMPLEMENTATION FROM orchestrator.py:792-808]
    pass  # Replace with full implementation
```

---

### STEP 3: Extract Configuration (config.py)

**Create:** `orchestrator/config.py`

**Content to Extract:**
- Lines 83-136: `_load_config` method
- Lines 137-156: `_expand_environment_variables` method (now uses utils.config_expansion)

**Code:**
```python
"""Configuration loading and management for orchestrator."""

import logging
import os
import yaml
from pathlib import Path
from typing import Dict

from utils.error_handler import ConversionError
from utils.config_expansion import expand_environment_variables

logger = logging.getLogger(__name__)


def load_config(config_path: str) -> Dict:
    """
    Load configuration from YAML file with environment variable expansion.

    SECURITY FIX: Implements ${VAR} environment variable expansion

    Args:
        config_path: Path to YAML configuration file

    Returns:
        Configuration dictionary

    Raises:
        ConversionError: If configuration cannot be loaded
    """
    try:
        config_file = Path(config_path)

        if not config_file.exists():
            raise ConversionError(f"Configuration file not found: {config_path}")

        # Read raw YAML
        with open(config_file, 'r', encoding='utf-8') as f:
            config_text = f.read()

        # Expand environment variables using centralized utility
        expanded_text = expand_environment_variables(config_text, strict=False)

        # Parse YAML
        config = yaml.safe_load(expanded_text)

        if not isinstance(config, dict):
            raise ConversionError(f"Invalid configuration format in {config_path}")

        logger.info(f"[OK] Configuration loaded from {config_path}")
        return config

    except ConversionError:
        raise  # Re-raise our custom errors
    except Exception as e:
        raise ConversionError(f"Failed to load configuration: {e}")
```

---

### STEP 4: Extract Component Initialization (initializer.py)

**Create:** `orchestrator/initializer.py`

**Content to Extract:**
- Lines 157-196: `initialize_components` method

**Code:**
```python
"""Component initialization for orchestrator."""

import logging
from typing import Dict
from anthropic import AsyncAnthropic

from components.github_scanner import GitHubParserScanner
from components.claude_analyzer import ClaudeParserAnalyzer
from components.lua_generator import ClaudeLuaGenerator
from components.rag_knowledge import RAGKnowledgeBase
from components.rag_assistant import ClaudeRAGAssistant
from components.observo_client import ObservoAPIClient
from components.github_automation import ClaudeGitHubAutomation

logger = logging.getLogger(__name__)


async def initialize_components(config: Dict) -> Dict[str, object]:
    """
    Initialize all components with async support.

    Args:
        config: Configuration dictionary

    Returns:
        Dictionary of initialized components
    """
    logger.info("[INIT] Initializing components...")

    components = {}

    # [COPY ENTIRE IMPLEMENTATION FROM orchestrator.py:157-196]
    # This includes:
    # - Claude client setup
    # - GitHub scanner
    # - Claude analyzer
    # - Lua generator
    # - RAG knowledge base
    # - RAG assistant
    # - Observo client
    # - GitHub automation

    logger.info("[OK] All components initialized")
    return components
```

---

### STEP 5: Extract Phase 1 (phase_1_scanner.py)

**Create:** `orchestrator/phase_1_scanner.py`

**Content to Extract:**
- Lines 322-361: `_phase_1_scan_parsers` method

**Code:**
```python
"""Phase 1: Parser Scanning - Scan SentinelOne parsers from GitHub."""

import logging
from typing import List, Dict
from datetime import datetime

logger = logging.getLogger(__name__)


async def scan_parsers(scanner, config: Dict, statistics: Dict) -> List[Dict]:
    """
    Phase 1: Scan SentinelOne parsers from GitHub repository.

    Args:
        scanner: GitHubParserScanner instance
        config: Configuration dictionary
        statistics: Statistics tracking dictionary

    Returns:
        List of scanned parser dictionaries

    Raises:
        Exception: If scanning fails
    """
    phase_start = datetime.now()
    logger.info("\n" + "=" * 70)
    logger.info("PHASE 1: Scanning SentinelOne Parsers")
    logger.info("=" * 70)

    # [COPY ENTIRE METHOD IMPLEMENTATION FROM orchestrator.py:322-361]
    pass  # Replace with full implementation

    phase_end = datetime.now()
    phase_duration = (phase_end - phase_start).total_seconds()
    statistics["phase_timings"]["phase_1_scan"] = phase_duration

    logger.info(f"[OK] Phase 1 complete: {len(parsers)} parsers scanned in {phase_duration:.1f}s")
    return parsers
```

---

### STEP 6: Extract Phase 2 (phase_2_analyzer.py)

**Create:** `orchestrator/phase_2_analyzer.py`

**Content to Extract:**
- Lines 362-407: `_phase_2_analyze_parsers` method

**Code:**
```python
"""Phase 2: Parser Analysis - Analyze parsers with Claude AI."""

import logging
from typing import List, Dict
from datetime import datetime

logger = logging.getLogger(__name__)


async def analyze_parsers(
    analyzer,
    parsers: List[Dict],
    statistics: Dict
) -> List[Dict]:
    """
    Phase 2: Analyze parsers using Claude AI.

    Args:
        analyzer: ClaudeParserAnalyzer instance
        parsers: List of parser dictionaries from Phase 1
        statistics: Statistics tracking dictionary

    Returns:
        List of analyzed parser dictionaries

    Raises:
        Exception: If analysis fails
    """
    phase_start = datetime.now()
    logger.info("\n" + "=" * 70)
    logger.info("PHASE 2: Analyzing Parsers with Claude AI")
    logger.info("=" * 70)

    # [COPY ENTIRE METHOD IMPLEMENTATION FROM orchestrator.py:362-407]
    pass  # Replace with full implementation

    phase_end = datetime.now()
    phase_duration = (phase_end - phase_start).total_seconds()
    statistics["phase_timings"]["phase_2_analyze"] = phase_duration

    logger.info(f"[OK] Phase 2 complete: {len(analyses)} parsers analyzed in {phase_duration:.1f}s")
    return analyses
```

---

### STEP 7: Extract Phase 3 (phase_3_generator.py)

**Create:** `orchestrator/phase_3_generator.py`

**Content to Extract:**
- Lines 408-476: `_phase_3_generate_lua` method

**Code:**
```python
"""Phase 3: Lua Generation - Generate Lua transformations from analyzed parsers."""

import logging
from typing import List, Dict
from datetime import datetime

logger = logging.getLogger(__name__)


async def generate_lua(
    lua_generator,
    template_registry,
    validator,
    metadata_builder,
    analyses: List[Dict],
    statistics: Dict
) -> List[Dict]:
    """
    Phase 3: Generate Lua code from analyzed parsers.

    Args:
        lua_generator: ClaudeLuaGenerator instance
        template_registry: ObservoLuaTemplateRegistry instance
        validator: PipelineValidator instance
        metadata_builder: AISIEMMetadataBuilder instance
        analyses: List of analyzed parser dictionaries from Phase 2
        statistics: Statistics tracking dictionary

    Returns:
        List of Lua generation results

    Raises:
        Exception: If Lua generation fails
    """
    phase_start = datetime.now()
    logger.info("\n" + "=" * 70)
    logger.info("PHASE 3: Generating Lua Code")
    logger.info("=" * 70)

    # [COPY ENTIRE METHOD IMPLEMENTATION FROM orchestrator.py:408-476]
    pass  # Replace with full implementation

    phase_end = datetime.now()
    phase_duration = (phase_end - phase_start).total_seconds()
    statistics["phase_timings"]["phase_3_generate"] = phase_duration

    logger.info(f"[OK] Phase 3 complete: {len(lua_parsers)} Lua scripts generated in {phase_duration:.1f}s")
    return lua_parsers
```

---

### STEP 8: Extract Phase 4 (phase_4_deployer.py)

**Create:** `orchestrator/phase_4_deployer.py`

**Content to Extract:**
- Lines 477-638: `_phase_4_deploy_and_upload` method

**Code:**
```python
"""Phase 4: Deployment - Deploy pipelines to Observo and upload to GitHub."""

import logging
from typing import List, Dict
from datetime import datetime

logger = logging.getLogger(__name__)


async def deploy_and_upload(
    observo_client,
    github_automation,
    output_manager,
    lua_parsers: List[Dict],
    config: Dict,
    statistics: Dict
) -> List[Dict]:
    """
    Phase 4: Deploy pipelines to Observo.ai and upload to GitHub.

    Args:
        observo_client: ObservoAPIClient instance
        github_automation: ClaudeGitHubAutomation instance
        output_manager: ParserOutputManager instance
        lua_parsers: List of Lua generation results from Phase 3
        config: Configuration dictionary
        statistics: Statistics tracking dictionary

    Returns:
        List of deployment results

    Raises:
        Exception: If deployment fails
    """
    phase_start = datetime.now()
    logger.info("\n" + "=" * 70)
    logger.info("PHASE 4: Deploying Pipelines and Uploading to GitHub")
    logger.info("=" * 70)

    # [COPY ENTIRE METHOD IMPLEMENTATION FROM orchestrator.py:477-638]
    # This is a long method (~160 lines) - copy it completely
    pass  # Replace with full implementation

    phase_end = datetime.now()
    phase_duration = (phase_end - phase_start).total_seconds()
    statistics["phase_timings"]["phase_4_deploy"] = phase_duration

    logger.info(f"[OK] Phase 4 complete: Deployed in {phase_duration:.1f}s")
    return deployment_results
```

---

### STEP 9: Extract Phase 5 (phase_5_reporter.py)

**Create:** `orchestrator/phase_5_reporter.py`

**Content to Extract:**
- Lines 639-660: `_phase_5_generate_report` method
- Lines 661-761: `_generate_comprehensive_report` method

**Code:**
```python
"""Phase 5: Report Generation - Create comprehensive conversion reports."""

import logging
from typing import List, Dict
from datetime import datetime

logger = logging.getLogger(__name__)


async def generate_report(
    deployment_results: List[Dict],
    output_dir,
    save_json_func,
    statistics: Dict
) -> None:
    """
    Phase 5: Generate comprehensive conversion report.

    Args:
        deployment_results: List of deployment results from Phase 4
        output_dir: Output directory path
        save_json_func: Function to save JSON files
        statistics: Statistics tracking dictionary
    """
    phase_start = datetime.now()
    logger.info("\n" + "=" * 70)
    logger.info("PHASE 5: Generating Comprehensive Report")
    logger.info("=" * 70)

    # [COPY IMPLEMENTATION FROM orchestrator.py:639-660]
    pass  # Replace with full implementation

    phase_end = datetime.now()
    phase_duration = (phase_end - phase_start).total_seconds()
    statistics["phase_timings"]["phase_5_report"] = phase_duration

    logger.info(f"[OK] Phase 5 complete: Report generated in {phase_duration:.1f}s")


def generate_comprehensive_report(deployment_results: List[Dict]) -> str:
    """
    Generate detailed Markdown conversion report.

    Args:
        deployment_results: List of deployment results

    Returns:
        Markdown formatted report string
    """
    # [COPY ENTIRE METHOD IMPLEMENTATION FROM orchestrator.py:661-761]
    # This is ~100 lines of report generation logic
    pass  # Replace with full implementation
```

---

### STEP 10: Create Core Orchestrator (core.py)

**Create:** `orchestrator/core.py`

**Content:**
```python
"""Core orchestrator class - coordinates all conversion phases."""

import logging
from pathlib import Path
from typing import Dict
from datetime import datetime

from components.observo_lua_templates import ObservoLuaTemplateRegistry
from components.parser_output_manager import ParserOutputManager
from components.pipeline_validator import PipelineValidator
from components.ai_siem_metadata_builder import AISIEMMetadataBuilder
from utils.logger import ConversionLogger

from .config import load_config
from .initializer import initialize_components
from .phase_1_scanner import scan_parsers
from .phase_2_analyzer import analyze_parsers
from .phase_3_generator import generate_lua
from .phase_4_deployer import deploy_and_upload
from .phase_5_reporter import generate_report
from .utils import save_statistics, display_final_statistics

logger = logging.getLogger(__name__)


class ConversionSystemOrchestrator:
    """Main orchestrator for SentinelOne to Observo.ai conversion."""

    def __init__(self, config_path: str = "config.yaml"):
        """
        Initialize orchestrator with configuration.

        Args:
            config_path: Path to YAML configuration file
        """
        self.config_path = config_path
        self.config = load_config(config_path)

        # Initialize logging
        self.logger_system = ConversionLogger(self.config)
        self.logger = ConversionLogger.get_logger("orchestrator")

        # Initialize statistics
        self.statistics = {
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "parsers_scanned": 0,
            "parsers_analyzed": 0,
            "lua_generated": 0,
            "pipelines_deployed": 0,
            "github_uploads": 0,
            "errors": [],
            "phase_timings": {}
        }

        # Output directory
        self.output_dir = Path("output")
        self.output_dir.mkdir(exist_ok=True)

        # Component placeholders (initialized asynchronously)
        self.scanner = None
        self.analyzer = None
        self.lua_generator = None
        self.knowledge_base = None
        self.rag_assistant = None
        self.observo_client = None
        self.github_automation = None

        # DIRECTOR REQUIREMENTS: New components
        self.template_registry = ObservoLuaTemplateRegistry()
        self.output_manager = ParserOutputManager(self.output_dir)
        self.validator = PipelineValidator(self.config)
        self.metadata_builder = AISIEMMetadataBuilder()

    async def run_complete_conversion(self):
        """
        Execute complete 5-phase conversion workflow.

        Phases:
        1. Scan parsers from GitHub
        2. Analyze parsers with Claude
        3. Generate Lua code
        4. Deploy to Observo.ai and upload to GitHub
        5. Generate comprehensive report
        """
        conversion_start = datetime.now()
        logger.info("\n" + "=" * 70)
        logger.info("STARTING COMPLETE CONVERSION PROCESS")
        logger.info("=" * 70)

        try:
            # Initialize all components
            await self._initialize_all_components()

            # Execute Phase 1
            parsers = await scan_parsers(
                self.scanner,
                self.config,
                self.statistics
            )

            # Execute Phase 2
            analyses = await analyze_parsers(
                self.analyzer,
                parsers,
                self.statistics
            )

            # Execute Phase 3
            lua_parsers = await generate_lua(
                self.lua_generator,
                self.template_registry,
                self.validator,
                self.metadata_builder,
                analyses,
                self.statistics
            )

            # Execute Phase 4
            deployment_results = await deploy_and_upload(
                self.observo_client,
                self.github_automation,
                self.output_manager,
                lua_parsers,
                self.config,
                self.statistics
            )

            # Execute Phase 5
            await generate_report(
                deployment_results,
                self.output_dir,
                self._save_json_wrapper,
                self.statistics
            )

            # Finalize
            conversion_end = datetime.now()
            total_duration = (conversion_end - conversion_start).total_seconds()

            self.statistics["end_time"] = conversion_end.isoformat()
            self.statistics["total_duration_seconds"] = total_duration

            # Save and display statistics
            save_statistics(self.statistics, self.output_dir)
            display_final_statistics(self.statistics)

            logger.info("\n" + "=" * 70)
            logger.info(f"[SUCCESS] Conversion complete in {total_duration:.1f}s")
            logger.info("=" * 70)

        except Exception as e:
            self.statistics["errors"].append(str(e))
            logger.error(f"[ERROR] Conversion failed: {e}")
            raise

        finally:
            await self._cleanup()

    async def _initialize_all_components(self):
        """Initialize all conversion components."""
        components = await initialize_components(self.config)

        self.scanner = components.get("scanner")
        self.analyzer = components.get("analyzer")
        self.lua_generator = components.get("lua_generator")
        self.knowledge_base = components.get("knowledge_base")
        self.rag_assistant = components.get("rag_assistant")
        self.observo_client = components.get("observo_client")
        self.github_automation = components.get("github_automation")

    def _save_json_wrapper(self, data, filename):
        """Wrapper for utils.save_json to match expected signature."""
        from .utils import save_json
        filepath = self.output_dir / filename
        save_json(data, str(filepath))

    async def _cleanup(self):
        """Cleanup resources before exit."""
        logger.info("[CLEANUP] Cleaning up resources...")

        # Close async clients
        if self.observo_client:
            await self.observo_client.close()
        if self.github_automation:
            await self.github_automation.close()

        logger.info("[OK] Cleanup complete")
```

---

### STEP 11: Update Root orchestrator.py to Wrapper

**Modify:** `orchestrator.py`

Replace entire content with:

```python
"""
Orchestrator - Backward Compatibility Wrapper

DEPRECATED: This file now imports from orchestrator module.
For new code, import directly from orchestrator:
    from orchestrator import ConversionSystemOrchestrator

This wrapper maintains backward compatibility with existing code.
"""

from orchestrator import ConversionSystemOrchestrator

# Keep main function for backward compatibility
import asyncio


async def main():
    """Main entry point (backward compatibility)."""
    orchestrator = ConversionSystemOrchestrator()
    await orchestrator.run_complete_conversion()


if __name__ == "__main__":
    asyncio.run(main())


__all__ = ['ConversionSystemOrchestrator', 'main']
```

---

## Verification Checklist

### 1. File Structure Check
```bash
ls -la orchestrator/
# Should show all 9 module files
```

### 2. Import Verification
```python
from orchestrator import ConversionSystemOrchestrator  # New
import orchestrator  # Old (should still work)
print("✓ Imports successful")
```

### 3. Syntax Check
```bash
python -m py_compile orchestrator/*.py
```

### 4. Entry Point Test
```bash
python main.py --help  # Should work
```

### 5. Module Size Check
```bash
wc -l orchestrator/*.py
# Each should be 80-180 lines
```

---

## Rollback Instructions

```bash
git checkout -- orchestrator.py
rm -rf orchestrator/
```

---

## Success Criteria

- [ ] All 9 modules created in `orchestrator/`
- [ ] Original file reduced to <50 lines
- [ ] No syntax errors
- [ ] main.py works without changes
- [ ] continuous_conversion_service.py imports work
- [ ] All 5 phases execute correctly
- [ ] Statistics tracked correctly
- [ ] Reports generate successfully

---

**EXECUTION COMMAND FOR HAIKU AGENT:**
```
Read this file completely, execute all steps sequentially, verify at each checkpoint, and report status.
```

**END OF AGENT 2 PROMPT**
