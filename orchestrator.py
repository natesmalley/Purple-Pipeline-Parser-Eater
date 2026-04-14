"""
Orchestrator - Backward Compatibility Wrapper

DEPRECATED: This file now imports from the orchestrator module.
For new code, import directly from orchestrator:
    from orchestrator import ConversionSystemOrchestrator

This wrapper maintains backward compatibility with existing code.

The orchestrator has been refactored into modular components:
    - orchestrator/core.py - Main orchestrator class
    - orchestrator/config.py - Configuration loading
    - orchestrator/initializer.py - Component initialization
    - orchestrator/parser_scanner.py - Phase 1: Parser scanning
    - orchestrator/parser_analyzer.py - Phase 2: Parser analysis
    - orchestrator/phase3_generate_lua.py - Phase 3: Lua generation
    - orchestrator/pipeline_deployer.py - Phase 4: Pipeline deployment
    - orchestrator/report_generator.py - Phase 5: Report generation
    - orchestrator/utils.py - Utility functions
"""

import asyncio
import logging

from orchestrator import ConversionSystemOrchestrator

logger = logging.getLogger(__name__)


async def main():
    """Main entry point (backward compatibility)."""
    try:
        orchestrator = ConversionSystemOrchestrator("config.yaml")
        await orchestrator.run_complete_conversion()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())


__all__ = ['ConversionSystemOrchestrator', 'main']
