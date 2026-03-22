#!/usr/bin/env python3
"""Batch Agentic Lua Generator — runs the agentic LLM pipeline across multiple parsers.

Usage:
    python scripts/batch_agent_generate.py --mode syslog --threshold 70
    python scripts/batch_agent_generate.py --mode all --force
    python scripts/batch_agent_generate.py --parsers cisco_asa,okta_authentication
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from components.agentic_lua_generator import AgenticLuaGenerator, AgentLuaCache

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("batch_agent")

DEFAULT_OUTPUT = Path("output/batch_agent_results.json")
DEFAULT_PARSER_SOURCE = Path("output/04_deployment_results.json")
ALT_PARSER_SOURCE = Path("output/02_analyzed_parsers.json")
PER_PARSER_TIMEOUT = 120  # seconds


def load_parser_entries(mode: str, specific_parsers: list = None) -> list:
    """Load parser entries from the pipeline output files."""
    entries = []

    for source in [DEFAULT_PARSER_SOURCE, ALT_PARSER_SOURCE]:
        if source.exists():
            try:
                data = json.loads(source.read_text())
                if isinstance(data, list):
                    entries = data
                elif isinstance(data, dict):
                    entries = data.get("parsers", data.get("results", data.get("entries", [])))
                break
            except Exception as e:
                logger.warning("Failed to load %s: %s", source, e)

    if not entries:
        # Scan output directories for parser configs
        output_dir = Path("output")
        for parser_dir in sorted(output_dir.iterdir()):
            if parser_dir.is_dir() and not parser_dir.name.startswith("."):
                config_path = parser_dir / "parser_config.json"
                if config_path.exists():
                    try:
                        config = json.loads(config_path.read_text())
                        entries.append({
                            "parser_name": parser_dir.name,
                            "config": config,
                            "ingestion_mode": config.get("ingestion_mode", "push"),
                        })
                    except Exception:
                        pass

    # Filter by mode
    if mode == "syslog":
        entries = [e for e in entries if e.get("ingestion_mode") == "syslog"]
    elif mode == "push":
        entries = [e for e in entries if e.get("ingestion_mode") != "syslog"]
    # mode == "all" keeps everything

    # Filter by specific parsers
    if specific_parsers:
        names = set(p.strip().lower() for p in specific_parsers)
        entries = [e for e in entries if e.get("parser_name", "").lower() in names]

    return entries


def run_batch(
    entries: list,
    api_key: str,
    model: str,
    threshold: int,
    max_iterations: int,
    force: bool,
) -> dict:
    """Run the agentic generator across all parser entries."""
    generator = AgenticLuaGenerator(
        api_key=api_key,
        model=model,
        max_iterations=max_iterations,
        score_threshold=threshold,
    )

    results = {
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "config": {
            "model": model,
            "threshold": threshold,
            "max_iterations": max_iterations,
            "force_regenerate": force,
        },
        "parsers": [],
        "summary": {
            "total": len(entries),
            "accepted": 0,
            "needs_review": 0,
            "failed": 0,
            "errors": 0,
            "skipped": 0,
        },
    }

    for i, entry in enumerate(entries, 1):
        parser_name = entry.get("parser_name", f"unknown_{i}")
        logger.info("=" * 60)
        logger.info("[%d/%d] Processing: %s", i, len(entries), parser_name)

        start = time.time()
        try:
            result = generator.generate(entry, force_regenerate=force)
            elapsed = time.time() - start

            score = result.get("confidence_score", 0)
            grade = result.get("confidence_grade", "F")

            # Categorize
            if result.get("error"):
                category = "error"
                results["summary"]["errors"] += 1
            elif score >= threshold:
                category = "accepted"
                results["summary"]["accepted"] += 1
            elif score >= 50:
                category = "needs_review"
                results["summary"]["needs_review"] += 1
            else:
                category = "failed"
                results["summary"]["failed"] += 1

            results["parsers"].append({
                "parser_name": parser_name,
                "score": score,
                "grade": grade,
                "category": category,
                "iterations": result.get("iterations", 0),
                "elapsed_seconds": round(elapsed, 2),
                "error": result.get("error"),
            })

            logger.info(
                "  Result: score=%d%% grade=%s category=%s time=%.1fs",
                score, grade, category, elapsed,
            )

        except Exception as e:
            elapsed = time.time() - start
            logger.error("  Error: %s", e)
            results["summary"]["errors"] += 1
            results["parsers"].append({
                "parser_name": parser_name,
                "score": 0,
                "grade": "F",
                "category": "error",
                "error": str(e),
                "elapsed_seconds": round(elapsed, 2),
            })

    results["completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return results


def print_summary(results: dict):
    """Print a human-readable summary."""
    summary = results["summary"]
    total = summary["total"]

    print("\n" + "=" * 60)
    print("BATCH GENERATION SUMMARY")
    print("=" * 60)
    print(f"Total parsers: {total}")
    print(f"  Accepted (>= threshold): {summary['accepted']}")
    print(f"  Needs review (50-69%):   {summary['needs_review']}")
    print(f"  Failed (< 50%):          {summary['failed']}")
    print(f"  Errors:                  {summary['errors']}")

    if total > 0:
        accept_rate = summary["accepted"] / total * 100
        print(f"\nAcceptance rate: {accept_rate:.1f}%")

    # Top and bottom performers
    parsers = sorted(results["parsers"], key=lambda p: p.get("score", 0), reverse=True)
    if parsers:
        print("\nTop performers:")
        for p in parsers[:5]:
            print(f"  {p['parser_name']:40s} {p['score']:3d}% ({p['grade']})")

        failed = [p for p in parsers if p.get("category") in ("failed", "error")]
        if failed:
            print("\nNeeding attention:")
            for p in failed[:5]:
                err = f" - {p['error']}" if p.get("error") else ""
                print(f"  {p['parser_name']:40s} {p['score']:3d}% ({p['grade']}){err}")

    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Batch agentic Lua generation")
    parser.add_argument(
        "--mode", choices=["syslog", "push", "all"], default="all",
        help="Which parsers to process (default: all)",
    )
    parser.add_argument(
        "--parsers", type=str, default=None,
        help="Comma-separated list of specific parser names to process",
    )
    parser.add_argument(
        "--threshold", type=int, default=70,
        help="Minimum score to accept (default: 70)",
    )
    parser.add_argument(
        "--max-iterations", type=int, default=3,
        help="Max refinement iterations per parser (default: 3)",
    )
    parser.add_argument(
        "--model", type=str, default="claude-sonnet-4-20250514",
        help="Claude model to use",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Force regeneration (ignore cache)",
    )
    parser.add_argument(
        "--output", type=str, default=str(DEFAULT_OUTPUT),
        help="Output file for batch results",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="List parsers that would be processed without running",
    )

    args = parser.parse_args()

    # Get API key
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key and not args.dry_run:
        print("Error: ANTHROPIC_API_KEY environment variable not set")
        sys.exit(1)

    # Load parser entries
    specific = args.parsers.split(",") if args.parsers else None
    entries = load_parser_entries(args.mode, specific)

    if not entries:
        print(f"No parsers found for mode={args.mode}")
        sys.exit(1)

    print(f"Found {len(entries)} parsers for mode={args.mode}")

    if args.dry_run:
        print("\nWould process:")
        for e in entries:
            name = e.get("parser_name", "unknown")
            mode = e.get("ingestion_mode", "unknown")
            print(f"  {name} (mode={mode})")
        sys.exit(0)

    # Run batch
    results = run_batch(
        entries=entries,
        api_key=api_key,
        model=args.model,
        threshold=args.threshold,
        max_iterations=args.max_iterations,
        force=args.force,
    )

    # Write results
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nResults written to: {output_path}")

    # Print summary
    print_summary(results)


if __name__ == "__main__":
    main()
