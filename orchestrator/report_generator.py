"""Phase 5: Report Generation - Create comprehensive conversion reports."""

import json
import logging
from typing import List, Dict
from datetime import datetime
from pathlib import Path

from utils.logger import ConversionLogger

logger = logging.getLogger(__name__)


async def generate_report(
    deployment_results: List[Dict],
    statistics: Dict,
    scanner,
    analyzer,
    lua_generator,
    observo_client,
    github_automation,
    output_dir: Path
) -> None:
    """
    Phase 5: Generate comprehensive conversion report.

    Args:
        deployment_results: List of deployment results from Phase 4
        statistics: Statistics tracking dictionary
        scanner: GitHubParserScanner instance (for statistics)
        analyzer: ClaudeParserAnalyzer instance (for statistics)
        lua_generator: ClaudeLuaGenerator instance (for statistics)
        observo_client: ObservoAPIClient instance (for statistics)
        github_automation: ClaudeGitHubAutomation instance (for statistics)
        output_dir: Output directory path
    """
    phase_start = datetime.now()
    ConversionLogger.log_phase("5: REPORT", "Generating comprehensive conversion report")

    try:
        report = generate_comprehensive_report(
            deployment_results,
            statistics,
            scanner,
            analyzer,
            lua_generator,
            observo_client,
            github_automation
        )

        # Save report
        report_path = output_dir / "conversion_report.md"
        report_path.write_text(report)

        statistics["phase_timings"]["phase_5"] = (datetime.now() - phase_start).total_seconds()

        ConversionLogger.log_phase("5: REPORT", "Completed - Report generated successfully")

        logger.info(f"[REPORT] Conversion report saved to: {report_path}")

    except Exception as e:
        logger.error(f"Phase 5 failed: {e}")
        # Non-critical failure, continue


def generate_comprehensive_report(
    deployment_results: List[Dict],
    statistics: Dict,
    scanner,
    analyzer,
    lua_generator,
    observo_client,
    github_automation
) -> str:
    """
    Generate detailed Markdown conversion report.

    Args:
        deployment_results: List of deployment results
        statistics: Statistics dictionary
        scanner: Scanner component for statistics
        analyzer: Analyzer component for statistics
        lua_generator: LUA generator component for statistics
        observo_client: Observo client for statistics
        github_automation: GitHub automation for statistics

    Returns:
        Markdown formatted report string
    """
    total_time = sum(statistics.get("phase_timings", {}).values())

    report = f"""# Purple Pipeline Parser Eater - Conversion Report

**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Total Runtime**: {total_time:.2f} seconds ({total_time/60:.2f} minutes)

## Executive Summary

- **Parsers Scanned**: {statistics.get('parsers_scanned', 0)}
- **Parsers Analyzed**: {statistics.get('parsers_analyzed', 0)}
- **LUA Generated**: {statistics.get('lua_generated', 0)}
- **Pipelines Deployed**: {statistics.get('pipelines_deployed', 0)}
- **GitHub Uploads**: {statistics.get('github_uploads', 0)}
- **Errors**: {len(statistics.get('errors', []))}

## Success Rates

- **Scan to Analysis**: {(statistics.get('parsers_analyzed', 0) / statistics.get('parsers_scanned', 1) * 100):.1f}%
- **Analysis to LUA**: {(statistics.get('lua_generated', 0) / statistics.get('parsers_analyzed', 1) * 100):.1f}%
- **LUA to Deployment**: {(statistics.get('pipelines_deployed', 0) / statistics.get('lua_generated', 1) * 100):.1f}%
- **Overall Success**: {(statistics.get('pipelines_deployed', 0) / statistics.get('parsers_scanned', 1) * 100):.1f}%

## Phase Timings

| Phase | Duration | Description |
|-------|----------|-------------|
| Phase 1 | {statistics.get('phase_timings', {}).get('phase_1', 0):.2f}s | Scanning parsers from GitHub |
| Phase 2 | {statistics.get('phase_timings', {}).get('phase_2', 0):.2f}s | Semantic analysis with Claude |
| Phase 3 | {statistics.get('phase_timings', {}).get('phase_3', 0):.2f}s | LUA code generation |
| Phase 4 | {statistics.get('phase_timings', {}).get('phase_4', 0):.2f}s | Deployment and GitHub upload |
| Phase 5 | {statistics.get('phase_timings', {}).get('phase_5', 0):.2f}s | Report generation |
| **Total** | **{total_time:.2f}s** | **Complete workflow** |

## Deployment Results

"""

    # Add deployment details
    for i, result in enumerate(deployment_results, 1):
        parser_id = result.get("parser_id", "unknown")
        ocsf_class = result.get("ocsf_classification", {}).get("class_name", "Unknown")
        complexity = result.get("parser_complexity", {}).get("level", "Unknown")
        pipeline_id = result.get("deployment", {}).get("pipeline_id", "unknown")

        # DIRECTOR REQUIREMENTS: Include validation status in report
        validation = result.get("validation", {})
        validation_status = validation.get("overall_status", "unknown")
        validation_errors = validation.get("error_count", 0)
        validation_warnings = validation.get("warning_count", 0)

        # Field extraction verification (Requirement 5)
        field_validation = validation.get("validations", {}).get("field_extraction", {})
        field_coverage = field_validation.get("coverage_percentage", "N/A")

        report += f"""### {i}. {parser_id}

- **OCSF Class**: {ocsf_class}
- **Complexity**: {complexity}
- **Pipeline ID**: `{pipeline_id}`
- **Status**: {result.get("deployment", {}).get("status", "unknown")}
- **Validation**: {validation_status} ({validation_errors} errors, {validation_warnings} warnings)
- **Field Coverage**: {field_coverage}%
- **Artifacts**: {len(result.get("artifact_paths", {}))} files created
- **GitHub**: {len(result.get("github", {}).get("uploaded_files", []))} files uploaded

"""

    # Add errors if any
    if statistics.get("errors"):
        report += "\n## Errors and Issues\n\n"
        for error in statistics["errors"]:
            report += f"- {error}\n"

    report += f"""

## Component Statistics

### GitHub Scanner
{json.dumps(scanner.get_statistics() if scanner else {}, indent=2)}

### Claude Analyzer
{json.dumps(analyzer.get_statistics() if analyzer else {}, indent=2)}

### LUA Generator
{json.dumps(lua_generator.get_statistics() if lua_generator else {}, indent=2)}

### Observo Client
{json.dumps(observo_client.get_statistics() if observo_client else {}, indent=2)}

### GitHub Automation
{json.dumps(github_automation.get_statistics() if github_automation else {}, indent=2)}

---
**Purple Pipeline Parser Eater v1.0.0**
"""

    return report
