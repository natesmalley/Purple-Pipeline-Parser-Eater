"""
Test script for retesting previously failed parsers after remediation
Tests only the parsers that failed in Phase 2 and Phase 3
"""

import asyncio
import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from orchestrator import ConversionSystemOrchestrator


# Category 3: JSON Serialization Failures (13 parsers - HIGH PRIORITY)
SERIALIZATION_FAILURES = [
    "aws_waf-latest",
    "marketplace-checkpointfirewall-latest",
    "marketplace-cortexfirewall-latest",
    "marketplace-crowdstrike-latest",
    "marketplace-fortigatefirewall-latest",
    "marketplace-googleworkspace-latest",
    "marketplace-mcafeelogs-latest",
    "marketplace-microsoft365-latest",
    "marketplace-okta-latest",
    "marketplace-sonicwallfirewall-latest",
    "marketplace-trendmicro-latest",
    "marketplace-watchguard-latest",
    "marketplace-zscalerlogs-latest",
]

# Category 2: Rate Limiting Failures - Phase 2 (10 parsers)
RATE_LIMIT_PHASE2_FAILURES = [
    "akamai_general-latest",
    "cisco_logs-latest",
    "cloudflare_inc_waf-lastest",
    "cloudflare_logs-latest",
    "dns_ocsf_logs-latest",
    "fortimanager_logs-latest",
    "singularityidentity_singularityidentity_logs-latest",
    "teleport_logs-latest",
    "vectra_ai_logs-latest",
    "vmware_vcenter_logs-latest",
]

# Category 1: JSON5 Parsing Failures (4 parsers - MANUAL REPAIR NEEDED)
JSON5_FAILURES = [
    "cisco_combo_logs-latest",
    "linux_system_logs-latest",
    "log4shell_detection_logs-latest",
    "manageengine_adauditplus_logs-latest",
]


async def test_parser_subset(orchestrator, parser_ids: list, test_name: str):
    """Test a specific subset of parsers"""
    logger.info(f"\n{'='*80}")
    logger.info(f"TESTING: {test_name}")
    logger.info(f"Total parsers to test: {len(parser_ids)}")
    logger.info(f"{'='*80}\n")

    results = {
        "total": len(parser_ids),
        "passed": 0,
        "failed": 0,
        "failed_parsers": []
    }

    # Initialize scanner session
    await orchestrator.scanner.initialize()

    # Scan parsers
    logger.info("[PHASE 1] Scanning parsers...")
    all_parsers = await orchestrator.scanner.scan_parsers()

    # Filter to only our test parsers
    test_parsers = [p for p in all_parsers if p.get("parser_id") in parser_ids]
    logger.info(f"Found {len(test_parsers)}/{len(parser_ids)} parsers to test")

    if len(test_parsers) == 0:
        logger.warning(f"No parsers found for test: {test_name}")
        return results

    # Analyze parsers
    logger.info(f"\n[PHASE 2] Analyzing {len(test_parsers)} parsers...")
    try:
        analyses = await orchestrator.analyzer.batch_analyze_parsers(
            test_parsers,
            batch_size=5,
            max_concurrent=3
        )

        results["passed"] = len(analyses)
        results["failed"] = len(test_parsers) - len(analyses)

        # Identify which parsers failed
        successful_ids = {a.parser_id for a in analyses}
        for parser_id in parser_ids:
            if parser_id not in successful_ids:
                results["failed_parsers"].append(parser_id)

        logger.info(f"\n[RESULTS] {test_name}:")
        logger.info(f"  Passed: {results['passed']}/{results['total']} ({results['passed']/results['total']*100:.1f}%)")
        logger.info(f"  Failed: {results['failed']}/{results['total']}")

        if results["failed_parsers"]:
            logger.warning(f"  Failed parsers: {', '.join(results['failed_parsers'])}")
        else:
            logger.info(f"  ✅ ALL PARSERS PASSED!")

    except Exception as e:
        logger.error(f"Test failed with exception: {e}")
        results["failed"] = len(test_parsers)
        results["failed_parsers"] = parser_ids

    return results


async def main():
    """Run all remediation tests"""

    logger.info("""
╔════════════════════════════════════════════════════════════════════════╗
║  PURPLE PIPELINE PARSER EATER - REMEDIATION VALIDATION TESTS          ║
║  Testing Priority 0 & Priority 1 Fixes                                 ║
╚════════════════════════════════════════════════════════════════════════╝
""")

    # Initialize orchestrator
    try:
        orchestrator = ConversionSystemOrchestrator()
        await orchestrator.initialize_components()
    except Exception as e:
        logger.error(f"Failed to initialize orchestrator: {e}")
        return 1

    # Run test suites
    all_results = {}

    # Test 1: JSON Serialization Fixes (Priority 0)
    logger.info("\n" + "="*80)
    logger.info("TEST SUITE 1: JSON Serialization Fixes (Priority 0 - DateTimeEncoder)")
    logger.info("Expected: 100% success rate (13/13 parsers)")
    logger.info("="*80)

    all_results["serialization"] = await test_parser_subset(
        orchestrator,
        SERIALIZATION_FAILURES,
        "JSON Serialization Fixes"
    )

    # Test 2: Rate Limiting Fixes - Phase 2 (Priority 1)
    logger.info("\n" + "="*80)
    logger.info("TEST SUITE 2: Rate Limiting Fixes - Phase 2 (Priority 1)")
    logger.info("Expected: 100% success rate (10/10 parsers)")
    logger.info("="*80)

    all_results["rate_limit_phase2"] = await test_parser_subset(
        orchestrator,
        RATE_LIMIT_PHASE2_FAILURES,
        "Rate Limiting Fixes (Phase 2)"
    )

    # Generate final summary
    logger.info("\n" + "="*80)
    logger.info("FINAL TEST SUMMARY")
    logger.info("="*80)

    total_tested = 0
    total_passed = 0
    total_failed = 0

    for test_name, results in all_results.items():
        total_tested += results["total"]
        total_passed += results["passed"]
        total_failed += results["failed"]

        logger.info(f"\n{test_name}:")
        logger.info(f"  Total: {results['total']}")
        logger.info(f"  Passed: {results['passed']} ({results['passed']/results['total']*100:.1f}%)")
        logger.info(f"  Failed: {results['failed']}")

    logger.info(f"\n{'='*80}")
    logger.info(f"OVERALL RESULTS:")
    logger.info(f"  Total Tested: {total_tested}")
    logger.info(f"  Total Passed: {total_passed} ({total_passed/total_tested*100:.1f}%)")
    logger.info(f"  Total Failed: {total_failed}")
    logger.info(f"{'='*80}")

    if total_failed == 0:
        logger.info("\n✅ ALL REMEDIATION TESTS PASSED! Ready for full system test.")
        return 0
    else:
        logger.warning(f"\n⚠️  {total_failed} parsers still failing. Review logs for details.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
