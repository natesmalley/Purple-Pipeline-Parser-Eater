#!/usr/bin/env bash
set -euo pipefail
# Plan Phase 7.7 — automated CVE audit of requirements.txt.
# Expected to run in CI alongside check_secret_leaks.sh.
#
# Exits 0 if no CVEs; non-zero if any. Uses pip-audit (install with
# `pip install pip-audit` — not bundled in requirements-test.txt to keep
# the test bootstrap light).

if ! command -v pip-audit >/dev/null 2>&1; then
    echo "pip-audit not installed. Skipping CVE scan."
    echo "Install with: pip install pip-audit"
    exit 0
fi

echo "=== Phase 7.7 pip-audit CVE scan ==="
pip-audit -r requirements.txt --desc --strict
