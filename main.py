#!/usr/bin/env python3
"""
Purple Pipeline Parser Eater - Main Entry Point
SentinelOne to Observo.ai Parser Conversion System
"""
import asyncio
import sys
import argparse
from pathlib import Path
from typing import Any

from orchestrator import ConversionSystemOrchestrator
from utils.logger import ConversionLogger


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Purple Pipeline Parser Eater - Convert SentinelOne parsers to Observo.ai pipelines",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run full conversion with default config
  python main.py

  # Use custom configuration file
  python main.py --config custom_config.yaml

  # Dry run mode (no actual deployment)
  python main.py --dry-run

  # Process specific parser types only
  python main.py --parser-types community

  # Limit number of parsers to process
  python main.py --max-parsers 10

For more information, visit: https://github.com/your-org/purple-pipeline-parser-eater
        """
    )

    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Path to configuration file (default: config.yaml)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run in dry-run mode without actual deployment"
    )

    parser.add_argument(
        "--max-parsers",
        type=int,
        help="Maximum number of parsers to process"
    )

    parser.add_argument(
        "--parser-types",
        type=str,
        nargs="+",
        choices=["community", "sentinelone"],
        help="Parser types to process (community, sentinelone)"
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    parser.add_argument(
        "--version",
        action="version",
        version="Purple Pipeline Parser Eater v1.0.0"
    )

    return parser.parse_args()


def display_banner() -> None:
    """Display application banner."""
    banner = """
    ========================================================================

         PURPLE PIPELINE PARSER EATER v1.0.0
         SentinelOne -> Observo.ai Conversion System

    ========================================================================

    * Convert SentinelOne parsers to Observo.ai pipelines with Claude AI
    * 165+ parsers - Semantic analysis - Optimized LUA generation
    * Automated deployment - Intelligent documentation - RAG assistance

    """
    print(banner)


async def run_conversion(args: argparse.Namespace) -> int:
    """
    Run the conversion process.

    Args:
        args: Parsed command line arguments

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    try:
        # Initialize orchestrator
        orchestrator = ConversionSystemOrchestrator(args.config)

        # Apply CLI overrides
        if args.max_parsers:
            orchestrator.config["processing"]["max_parsers"] = args.max_parsers

        if args.parser_types:
            orchestrator.config["processing"]["parser_types"] = args.parser_types

        if args.verbose:
            orchestrator.config["logging"]["level"] = "DEBUG"

        # Apply dry-run mode (force mock mode in components)
        if args.dry_run:
            print("[DRY-RUN] No actual deployments will occur\n")
            # Force mock mode by setting invalid API keys that components will detect
            orchestrator.config["observo"]["api_key"] = "dry-run-mode"
            orchestrator.config["github"]["token"] = "dry-run-mode"

        # Run conversion
        await orchestrator.run_complete_conversion()

        return 0

    except KeyboardInterrupt:
        print("\n\n[!] Conversion interrupted by user")
        return 130
    except Exception as e:
        print(f"\n\n[ERROR] Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return 1


def main() -> int:
    """
    Main entry point.

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    # Parse arguments
    args = parse_arguments()

    # Display banner
    display_banner()

    # Verify configuration file exists
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"[ERROR] Configuration file not found: {args.config}")
        print("\n[INFO] Create a config.yaml file with your API keys:")
        print("   - Anthropic API key (Claude)")
        print("   - Observo.ai API key")
        print("   - GitHub token (optional)")
        print("\nSee config.yaml.example for template")
        return 1

    # Check for dry-run mode
    if args.dry_run:
        print("[DRY-RUN] Running in DRY-RUN mode (no actual deployment)")
        print()

    # Run conversion
    try:
        exit_code = asyncio.run(run_conversion(args))
        return exit_code
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
