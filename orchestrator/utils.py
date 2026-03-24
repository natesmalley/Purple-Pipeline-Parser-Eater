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
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def build_manifest_metadata(
    parser: Dict[str, Any],
    validation_results: Dict[str, Any],
    config: Dict[str, Any],
    mode: str = "stable",
) -> Dict[str, Any]:
    """
    Construct manifest metadata for stable or canary deployment.

    DIRECTOR REQUIREMENTS:
    - Requirement 1: Semantic versioning
    - Requirement 3: Comprehensive manifest with all metadata
    - Requirement 6: AI-SIEM classification metadata

    Args:
        parser: Parser data dictionary
        validation_results: Validation results dictionary
        config: Configuration dictionary
        mode: Deployment mode ("stable" or "canary")

    Returns:
        Manifest metadata dictionary
    """
    canary_config = config.get("canary", {})
    parser_canary = parser.get("canary_config", {})

    base_semantic = parser.get("version", "1.0.0")
    if mode == "canary":
        semantic = parser_canary.get(
            "semantic",
            parser.get("canary_version")
            or f"{base_semantic}{canary_config.get('semantic_suffix', '-canary')}"
        )
        canary_percentage = parser_canary.get("percentage", canary_config.get("percentage", 10))
    else:
        semantic = base_semantic
        canary_percentage = 0

    compatibility_defaults = {
        "min_dataplane_version": canary_config.get("min_dataplane_version", "0.30.0"),
        "ocsf_version": canary_config.get("ocsf_version", "1.5.0"),
    }

    extracted_fields = (
        validation_results
        .get("validations", {})
        .get("field_extraction", {})
        .get("extracted_fields", [])
    )

    manifest = {
        "manifest_version": parser.get("manifest_version", "1.0"),
        "parser_id": parser["parser_id"],
        "version": {
            "lua_sha256": hash_string(parser["lua_code"]),
            "semantic": semantic,
            "previous": parser.get("previous_version"),
            "changelog": parser.get("changelog", []),
        },
        "compatibility": {
            "min_dataplane_version": parser.get("compatibility", {}).get(
                "min_dataplane_version",
                compatibility_defaults["min_dataplane_version"],
            ),
            "ocsf_version": parser.get("compatibility", {}).get(
                "ocsf_version",
                compatibility_defaults["ocsf_version"],
            ),
        },
        "lua_metadata": {
            "file": parser.get("lua_metadata", {}).get("file", "transform.lua"),
            "entry_function": parser.get("lua_metadata", {}).get("entry_function", "processEvent"),
            "search_dirs": parser.get("lua_metadata", {}).get("search_dirs", ["ocsf"]),
            "estimated_memory_mb": parser.get("estimated_memory_mb"),
            "avg_execution_time_ms": parser.get("avg_execution_time_ms"),
        },
        "ocsf_output": {
            "class_uid": parser.get("ocsf_classification", {}).get("class_uid", 0),
            "class_name": parser.get("ocsf_classification", {}).get("class_name", "Unknown"),
            "extracted_fields": extracted_fields,
        },
        "source": {
            "repository": config.get("github", {}).get("source_repo_url", "unknown"),
            "parser_path": parser.get("github_path"),
            "git_commit": parser.get("git_commit"),
        },
        "deployment": {
            "deployed_at": datetime.now().isoformat(),
            "deployed_by": canary_config.get("deployed_by", "pppe"),
            "environment": canary_config.get("environment", "production"),
            "canary_percentage": canary_percentage,
        },
    }

    return manifest


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
    def json_serial(obj):
        """JSON serializer for objects not serializable by default json code"""
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        raise TypeError(f"Type {type(obj)} not serializable")

    try:
        stats_path = output_dir / "statistics.json"
        with open(stats_path, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, default=json_serial)
        logger.info(f"[STATS] Statistics saved to: {stats_path}")
    except Exception as e:
        logger.error(f"Failed to save statistics: {e}")
        raise


def display_final_statistics(stats: Dict) -> None:
    """
    Display final statistics summary.

    Args:
        stats: Statistics dictionary
    """
    logger.info("\n" + "=" * 80)
    logger.info("[STATS] FINAL STATISTICS")
    logger.info("=" * 80)
    logger.info(f"Parsers Scanned:      {stats.get('parsers_scanned', 0)}")
    logger.info(f"Parsers Analyzed:     {stats.get('parsers_analyzed', 0)}")
    logger.info(f"LUA Generated:        {stats.get('lua_generated', 0)}")
    logger.info(f"Pipelines Deployed:   {stats.get('pipelines_deployed', 0)}")
    logger.info(f"GitHub Uploads:       {stats.get('github_uploads', 0)}")
    logger.info(f"Errors:               {len(stats.get('errors', []))}")
    logger.info("=" * 80)

    total_time = sum(stats.get('phase_timings', {}).values())
    logger.info(f"Total Runtime:        {total_time:.2f}s ({total_time/60:.2f} minutes)")
    logger.info("=" * 80 + "\n")
