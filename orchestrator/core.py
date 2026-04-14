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
from .parser_scanner import scan_parsers
from .parser_analyzer import analyze_parsers
from .phase3_generate_lua import generate_lua
from .pipeline_deployer import deploy_and_upload
from .report_generator import generate_report
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

        # Output directory (must be created before ParserOutputManager)
        self.output_dir = Path("output")
        self.output_dir.mkdir(exist_ok=True)

        # Initialize components (will be set up in async context)
        self.claude_client = None
        self.scanner = None
        self.analyzer = None
        self.lua_generator = None
        self.knowledge_base = None
        self.rag_assistant = None
        self.observo_client = None
        self.github_automation = None

        # DIRECTOR REQUIREMENTS: New components for validation and metadata
        self.template_registry = ObservoLuaTemplateRegistry()  # Requirement 2
        self.output_manager = ParserOutputManager(self.output_dir)  # Requirement 3
        self.validator = PipelineValidator(self.config)  # Requirements 4 & 5
        self.metadata_builder = AISIEMMetadataBuilder()  # Requirement 6

    async def run_complete_conversion(self):
        """
        Execute complete conversion workflow.

        Phases:
        1. Scan parsers from GitHub
        2. Analyze parsers with Claude
        3. Generate Lua code
        4. Deploy to Observo.ai and upload to GitHub
        5. Generate comprehensive report
        """
        self.logger.info("[START] Starting Purple Pipeline Parser Eater conversion system")
        self.logger.info("=" * 80)

        try:
            # Initialize components
            await self._initialize_all_components()

            # Phase 1: Scan parsers
            parsers = await scan_parsers(
                self.scanner,
                self.config,
                self.statistics,
                self.output_dir
            )

            # Phase 2: Analyze parsers
            analyses = await analyze_parsers(
                self.analyzer,
                parsers,
                self.config,
                self.statistics,
                self.output_dir
            )

            # Phase 3: Generate LUA transformations
            lua_results = await generate_lua(
                self.lua_generator,
                self.template_registry,
                analyses,
                self.config,
                self.statistics,
                self.output_dir
            )

            # Phase 4: Deploy to Observo and upload to GitHub
            deployment_results = await deploy_and_upload(
                self.observo_client,
                self.github_automation,
                self.output_manager,
                self.validator,
                self.metadata_builder,
                self.rag_assistant,
                lua_results,
                self.config,
                self.statistics,
                self.output_dir
            )

            # Phase 5: Generate comprehensive final report
            await generate_report(
                deployment_results,
                self.statistics,
                self.scanner,
                self.analyzer,
                self.lua_generator,
                self.observo_client,
                self.github_automation,
                self.output_dir
            )

            # Cleanup
            await self._cleanup()

            self.statistics["end_time"] = datetime.now().isoformat()
            self.logger.info("=" * 80)
            self.logger.info("[OK] Conversion process completed successfully")
            display_final_statistics(self.statistics)

        except Exception as e:
            self.logger.error(f"[ERROR] Conversion process failed: {e}")
            self.statistics["errors"].append(str(e))
            raise
        finally:
            # Save statistics
            save_statistics(self.statistics, self.output_dir)

    async def _initialize_all_components(self):
        """Initialize all conversion components."""
        components = await initialize_components(self.config)

        self.claude_client = components.get("claude_client")
        self.scanner = components.get("scanner")
        self.analyzer = components.get("analyzer")
        self.lua_generator = components.get("lua_generator")
        self.knowledge_base = components.get("knowledge_base")
        self.rag_assistant = components.get("rag_assistant")
        self.observo_client = components.get("observo_client")
        self.github_automation = components.get("github_automation")

    async def _cleanup(self):
        """Cleanup resources before exit."""
        self.logger.info("[CLEANUP] Cleaning up resources...")

        if self.knowledge_base:
            self.knowledge_base.cleanup()

        self.logger.info("[OK] Cleanup complete")
