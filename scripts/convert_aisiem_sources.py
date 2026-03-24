#!/usr/bin/env python3
"""Fetch SentinelOne ai-siem parsers and generate conversion output for the workbench."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from components.ai_siem_pipeline_converter import AISIEMPipelineConverter


async def main():
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    converter = AISIEMPipelineConverter()
    print("Converting ai-siem parsers (fetching from GitHub)...")
    result = await converter.convert()

    out_path = output_dir / "ai_siem_parser_source_components.json"
    out_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")

    summary = result.get("summary", {})
    converted = result.get("converted", [])
    print(f"Done: {summary.get('converted_total', len(converted))} parsers converted")
    print(f"  Syslog: {summary.get('syslog_total', 0)}")
    print(f"  Push: {summary.get('push_total', 0)}")
    print(f"  Archive fallback: {summary.get('used_archive_fallback', False)}")
    print(f"Output: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
