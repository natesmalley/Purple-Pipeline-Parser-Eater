#!/usr/bin/env python3
"""
Demo Runner with Environment Variable Loading
Loads .env file and runs the 10-parser demo
"""
import os
import sys
from pathlib import Path


def load_env_file():
    """Load environment variables from .env file"""
    env_file = Path(".env")

    if not env_file.exists():
        print("[WARN] .env file not found")
        return

    print("[INFO] Loading environment variables from .env file...")

    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue

            # Parse KEY=VALUE
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()

                # Set environment variable
                os.environ[key] = value
                print(f"[OK] Set {key}")

    print()


def main():
    """Main entry point"""
    # Load .env file first
    load_env_file()

    # Now import and run the demo
    # (This must happen AFTER loading env vars)
    import asyncio
    from orchestrator import ConversionSystemOrchestrator

    async def run_demo():
        print("=" * 80)
        print("   PURPLE PIPELINE PARSER EATER - 10 PARSER DEMO")
        print("=" * 80)
        print()
        print("This demo will process 10 parsers to show the APM in action:")
        print("  1. Scan parsers from GitHub")
        print("  2. Analyze with Claude AI")
        print("  3. Generate Lua transformations")
        print("  4. Validate and create output files")
        print("  5. Show browser-based visualization")
        print()
        print("=" * 80)
        print()

        try:
            # Initialize orchestrator
            orchestrator = ConversionSystemOrchestrator("config.yaml")

            # Override config for demo - just 10 parsers
            orchestrator.config["processing"]["max_parsers"] = 10
            orchestrator.config["processing"]["batch_size"] = 5
            orchestrator.config["processing"]["max_concurrent"] = 2

            # Disable actual deployment for demo (dry-run mode)
            print("[DEMO MODE] Setting dry-run mode (no actual Observo deployment)")
            orchestrator.config["observo"]["api_key"] = "dry-run-demo-mode"
            print()

            # Run conversion
            await orchestrator.run_complete_conversion()

            print()
            print("=" * 80)
            print("[SUCCESS] Demo completed! Check the output folder for results:")
            print()
            print("  output/")
            print("    ├── 01_scanned_parsers.json     - Raw parser data from GitHub")
            print("    ├── 02_analyzed_parsers.json    - Claude AI analysis results")
            print("    ├── 03_lua_generated.json       - Generated Lua code")
            print("    ├── conversion_report.md        - Full conversion report")
            print("    ├── statistics.json             - Processing statistics")
            print("    └── [parser-name]/              - Individual parser outputs")
            print("        ├── analysis.json           - Parser analysis")
            print("        ├── transform.lua           - Lua transformation")
            print("        ├── pipeline.json           - Observo pipeline config")
            print("        └── validation_report.json  - Validation results")
            print()
            print("=" * 80)
            print()

            # Show where to view results in browser
            output_dir = Path("output")
            if output_dir.exists():
                parser_dirs = [d for d in output_dir.iterdir() if d.is_dir()]
                print(f"[INFO] Generated outputs for {len(parser_dirs)} parsers")
                print()
                print("To view in browser:")
                print("  1. Open viewer.html in your browser")
                print("  2. Or run: python -m http.server 8000")
                print("     Then visit: http://localhost:8000/viewer.html")
                print()

            return 0

        except KeyboardInterrupt:
            print("\n\n[!] Demo interrupted by user")
            return 130
        except Exception as e:
            print(f"\n\n[ERROR] Demo failed: {e}")
            import traceback
            traceback.print_exc()
            return 1

    return asyncio.run(run_demo())


if __name__ == "__main__":
    sys.exit(main())
