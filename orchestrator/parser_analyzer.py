"""Phase 2: Parser Analysis - Analyze parsers with Claude AI."""

import logging
from typing import List, Dict
from datetime import datetime
from pathlib import Path

from utils.logger import ConversionLogger
from .utils import save_json

logger = logging.getLogger(__name__)


async def analyze_parsers(
    analyzer,
    parsers: List[Dict],
    config: Dict,
    statistics: Dict,
    output_dir: Path
) -> List[Dict]:
    """
    Phase 2: Semantic analysis with Claude.

    Args:
        analyzer: ClaudeParserAnalyzer instance
        parsers: List of parser dictionaries from Phase 1
        config: Configuration dictionary
        statistics: Statistics tracking dictionary
        output_dir: Output directory path

    Returns:
        List of analyzed parser dictionaries

    Raises:
        Exception: If analysis fails
    """
    phase_start = datetime.now()
    ConversionLogger.log_phase("2: ANALYZE", f"Analyzing {len(parsers)} parsers with Claude AI")

    try:
        # Get batch processing configuration
        batch_size = config.get("processing", {}).get("batch_size", 10)
        max_concurrent = config.get("processing", {}).get("max_concurrent", 3)

        # Batch analyze parsers
        analyses = await analyzer.batch_analyze_parsers(
            parsers,
            batch_size=batch_size,
            max_concurrent=max_concurrent
        )

        # Convert to dict format and merge with parser data
        analyzed_parsers = []
        for analysis in analyses:
            # Find matching parser
            parser = next((p for p in parsers if p["parser_id"] == analysis.parser_id), None)
            if parser:
                # Merge analysis with parser data
                merged = {**parser, **analysis.to_dict()}
                analyzed_parsers.append(merged)

        statistics["parsers_analyzed"] = len(analyzed_parsers)
        statistics["phase_timings"]["phase_2"] = (datetime.now() - phase_start).total_seconds()

        # Save analyses
        save_json(analyzed_parsers, str(output_dir / "02_analyzed_parsers.json"))

        ConversionLogger.log_phase(
            "2: ANALYZE",
            f"Completed - {len(analyzed_parsers)} parsers analyzed",
            count=len(analyzed_parsers),
            success_rate=analyzer.get_statistics().get("success_rate", 0)
        )

        return analyzed_parsers

    except Exception as e:
        logger.error(f"Phase 2 failed: {e}")
        raise
