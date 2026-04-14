#!/usr/bin/env bash
set -euo pipefail
# Plan Phase 7.8 — broader secret-leak scan via gitleaks.
# Falls back to check_secret_leaks.sh if gitleaks is not installed.
#
# Installation:
#   macOS:    brew install gitleaks
#   Windows:  scoop install gitleaks
#   Linux:    see https://github.com/gitleaks/gitleaks/releases

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if command -v gitleaks >/dev/null 2>&1; then
    echo "=== Phase 7.8 gitleaks scan ==="
    gitleaks detect --no-git --source . --verbose
else
    echo "gitleaks not installed. Falling back to check_secret_leaks.sh"
    bash "${SCRIPT_DIR}/check_secret_leaks.sh"
fi
