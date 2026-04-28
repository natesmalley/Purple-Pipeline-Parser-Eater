#!/usr/bin/env python3
"""Milestone A A/B check — regenerate one parser with and without the
reference-library prompt injection, and compare confidence scores.

Uses Anthropic directly (regardless of what .env preferences say) because the
Milestone A wiring lives on the standard prompt path. OpenAI's gpt-5 branch
takes a different planning prompt and does not yet receive reference
implementations.

Usage:
    python scripts/ab_reference_library.py
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

# Load .env manually (no python-dotenv dependency required).
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
if ENV_PATH.exists():
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

from components.agentic_lua_generator import AgenticLuaGenerator

FIXTURE = Path("data/regression_fixtures/marco_2026_04_08/cisco_duo")
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5").strip()

if not API_KEY:
    print("ANTHROPIC_API_KEY not set in .env; skipping live A/B.")
    sys.exit(2)


def build_parser_entry() -> dict:
    sample = json.loads((FIXTURE / "sample.json").read_text())
    config = json.loads((FIXTURE / "parser_config.json").read_text())
    return {
        "parser_name": config["parser_name"],
        "declared_log_type": config.get("declared_log_type", ""),
        "ingestion_mode": "push",
        "raw_examples": [sample],
        "config": {
            "attributes": {
                "dataSource": {
                    "vendor": config.get("vendor", ""),
                    "product": config.get("product", ""),
                }
            },
            "fields": config.get("fields", []),
        },
    }


def run_once(ref_library_on: bool) -> dict:
    os.environ["HARNESS_REFERENCE_LIBRARY"] = "1" if ref_library_on else "0"
    gen = AgenticLuaGenerator(
        api_key=API_KEY,
        model=MODEL,
        provider="anthropic",
        max_iterations=2,
        score_threshold=70,
    )
    result = gen.generate(build_parser_entry(), force_regenerate=True)
    return {
        "reference_library": ref_library_on,
        "confidence_score": result.get("confidence_score"),
        "iterations": result.get("iterations"),
        "has_processEvent": "function processEvent" in (result.get("lua_code") or ""),
        "has_features_table": "FEATURES = {" in (result.get("lua_code") or ""),
        "has_field_orders": "FIELD_ORDERS" in (result.get("lua_code") or ""),
        "lua_line_count": len((result.get("lua_code") or "").splitlines()),
        "lint_score": (result.get("harness_report", {}).get("checks", {})
                       .get("lua_linting", {}).get("score")),
        "ocsf_class_uid_detected": (result.get("harness_report", {}).get("checks", {})
                                    .get("ocsf_alignment", {}).get("class_uid")),
    }


def main() -> int:
    results = {}
    print(f"Running A/B against Anthropic model: {MODEL}")
    print(f"Parser: cisco_duo (class 3002 Authentication)")
    print()
    for on in (False, True):
        label = "on" if on else "off"
        print(f"  run: HARNESS_REFERENCE_LIBRARY={label} ...", flush=True)
        results[label] = run_once(on)

    out_path = Path("output/ab_reference_library.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2))

    print()
    print("=== Results ===")
    print(json.dumps(results, indent=2))
    print()
    off = results["off"]
    on = results["on"]
    delta = (on["confidence_score"] or 0) - (off["confidence_score"] or 0)
    print(f"Confidence delta (on - off): {delta:+d}")
    print(f"Style markers (FEATURES/FIELD_ORDERS):")
    print(f"  off: FEATURES={off['has_features_table']}  FIELD_ORDERS={off['has_field_orders']}")
    print(f"  on : FEATURES={on['has_features_table']}   FIELD_ORDERS={on['has_field_orders']}")
    print(f"Written: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
