"""Phase 1: Parser Scanning - Scan SentinelOne parsers from GitHub."""

import logging
from typing import List, Dict
from datetime import datetime
from pathlib import Path

from utils.logger import ConversionLogger
from .utils import save_json

logger = logging.getLogger(__name__)


async def scan_parsers(scanner, config: Dict, statistics: Dict, output_dir: Path) -> List[Dict]:
    """
    Phase 1: Scan and retrieve parser configurations.

    DIRECTOR REQUIREMENT 1: Fetch parsers from GitHub.com/sentinel-one/ai-siem/parsers/

    Args:
        scanner: GitHubParserScanner instance
        config: Configuration dictionary
        statistics: Statistics tracking dictionary
        output_dir: Output directory path

    Returns:
        List of scanned parser dictionaries

    Raises:
        Exception: If scanning fails
    """
    phase_start = datetime.now()
    ConversionLogger.log_phase("1: SCAN", "Scanning SentinelOne parsers from GitHub")

    try:
        async with scanner:
            parsers = await scanner.scan_parsers()

        # Apply filters from configuration
        max_parsers = config.get("processing", {}).get("max_parsers", 165)
        parser_types = config.get("processing", {}).get("parser_types", ["community", "sentinelone"])

        filtered_parsers = [
            p for p in parsers
            if p.get("source_type") in parser_types
        ][:max_parsers]

        statistics["parsers_scanned"] = len(filtered_parsers)
        statistics["phase_timings"]["phase_1"] = (datetime.now() - phase_start).total_seconds()

        # Save scanned parsers
        save_json(filtered_parsers, str(output_dir / "01_scanned_parsers.json"))

        ConversionLogger.log_phase(
            "1: SCAN",
            f"Completed - {len(filtered_parsers)} parsers scanned",
            count=len(filtered_parsers)
        )

        return filtered_parsers

    except Exception as e:
        logger.error(f"Phase 1 failed: {e}")
        raise
