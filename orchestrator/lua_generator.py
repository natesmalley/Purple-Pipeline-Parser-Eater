"""Phase 3: Lua Generation - Generate Lua transformations from analyzed parsers."""

import logging
from typing import List, Dict
from datetime import datetime
from pathlib import Path

from utils.logger import ConversionLogger
from .utils import save_json

logger = logging.getLogger(__name__)


async def generate_lua(
    lua_generator,
    template_registry,
    analyses: List[Dict],
    config: Dict,
    statistics: Dict,
    output_dir: Path
) -> List[Dict]:
    """
    Phase 3: Generate optimized LUA transformation code.

    DIRECTOR REQUIREMENT 2: Use Observo LUA templates for consistent generation
    DIRECTOR REQUIREMENT 3: Generate per-parser artifacts (4 files each)

    Args:
        lua_generator: ClaudeLuaGenerator instance
        template_registry: ObservoLuaTemplateRegistry instance
        analyses: List of analyzed parser dictionaries from Phase 2
        config: Configuration dictionary
        statistics: Statistics tracking dictionary
        output_dir: Output directory path

    Returns:
        List of Lua generation results

    Raises:
        Exception: If Lua generation fails
    """
    phase_start = datetime.now()
    ConversionLogger.log_phase("3: GENERATE", f"Generating LUA code for {len(analyses)} parsers")

    try:
        # Get batch processing configuration
        batch_size = config.get("processing", {}).get("batch_size", 10)
        max_concurrent = config.get("processing", {}).get("max_concurrent", 3)

        # REQUIREMENT 2: Select appropriate template based on parser characteristics
        for analysis in analyses:
            parser_type = analysis.get("parser_type", "unknown")
            has_ocsf = analysis.get("ocsf_classification", {}).get("class_uid") is not None
            template = template_registry.get_template_for_parser(parser_type, has_ocsf)
            analysis["selected_template"] = template.name if template else None

        # Batch generate LUA
        lua_results = await lua_generator.batch_generate_lua(
            analyses,
            batch_size=batch_size,
            max_concurrent=max_concurrent
        )

        # Merge LUA results with analyses
        lua_parsers = []
        for lua_result in lua_results:
            # Find matching analysis
            analysis = next((a for a in analyses if a["parser_id"] == lua_result.parser_id), None)
            if analysis:
                merged = {**analysis, **lua_result.to_dict()}
                lua_parsers.append(merged)

        statistics["lua_generated"] = len(lua_parsers)
        statistics["phase_timings"]["phase_3"] = (datetime.now() - phase_start).total_seconds()

        # Save LUA results (aggregate file for backward compatibility)
        save_json(lua_parsers, str(output_dir / "03_lua_generated.json"))

        # REQUIREMENT 3: Save per-parser artifacts (4 files each)
        # Note: Full validation and metadata will be added in Phase 4
        # Here we just create the directory structure and save initial LUA
        for parser in lua_parsers:
            # Create per-parser directory
            parser_dir = output_dir / parser['parser_id']
            parser_dir.mkdir(exist_ok=True)

            # Save LUA file (artifact 2/4)
            lua_file = parser_dir / "transform.lua"
            lua_file.write_text(parser["lua_code"])

        ConversionLogger.log_phase(
            "3: GENERATE",
            f"Completed - {len(lua_parsers)} LUA transformations generated",
            count=len(lua_parsers),
            success_rate=lua_generator.get_statistics().get("success_rate", 0)
        )

        return lua_parsers

    except Exception as e:
        logger.error(f"Phase 3 failed: {e}")
        raise
