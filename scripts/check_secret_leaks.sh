#!/usr/bin/env bash
# Phase 5.D - secret-leak CI guard.
#
# Grep the repo for known-leaked tokens and HEC-token-shaped patterns.
# Exits non-zero on any match. Documented in CI config.
#
# Usage: bash scripts/check_secret_leaks.sh [<path>...]
#   Default path is the repo root.

set -euo pipefail

PATHS=("$@")
if [ ${#PATHS[@]} -eq 0 ]; then
    PATHS=(".")
fi

# The specific known-leaked token from observo-dataPlane/s1_hec.yaml:23.
# Phase 0 confirmed this is NOT in our repo; Phase 5.D prevents future commits.
# DO NOT treat this as a secret - it's a tombstone marker for pattern matching.
KNOWN_LEAKED_TOKEN="0_T5MMxAtfrW52"

# Files that are allowed to MENTION the token (documentation references +
# the guard's own files). Matched by basename.
ALLOWED_MENTIONS=(
    "TODO.md"
    "REVIEW_REPORT.md"
    "CLAUDE.md"
    "check_secret_leaks.sh"
    "test_secret_leak_guard.py"
)

# Directories to exclude from scanning entirely.
EXCLUDE_DIRS=(
    ".git"
    ".venv"
    ".venv-test"
    "__pycache__"
    "node_modules"
    ".pytest_cache"
    "output"
    "data"
)

EXCLUDE_ARGS=()
for d in "${EXCLUDE_DIRS[@]}"; do
    EXCLUDE_ARGS+=(--exclude-dir="$d")
done
EXCLUDE_ARGS+=(--exclude="*.pyc" --exclude="*.so" --exclude="*.dll" --exclude="*.exe" --exclude="*.bin")

is_allowed() {
    local path="$1"
    local base
    base="$(basename "$path")"
    for allow in "${ALLOWED_MENTIONS[@]}"; do
        if [ "$base" = "$allow" ]; then
            return 0
        fi
    done
    return 1
}

# Parse a grep -rn line into its path portion.
# Supports POSIX ("/path/file:42:content") and Windows ("C:\path\file:42:content")
# by stripping the trailing :LINENO:content using sed.
parse_grep_line() {
    local line="$1"
    printf '%s' "$line" | sed -E 's/:[0-9]+:.*$//'
}

fail=0

echo "=== Phase 5.D secret-leak scan ==="

# Step 1: known-leaked-token scan
for p in "${PATHS[@]}"; do
    hits=$(grep -rnI "${EXCLUDE_ARGS[@]}" "${KNOWN_LEAKED_TOKEN}" "$p" 2>/dev/null || true)
    if [ -n "$hits" ]; then
        while IFS= read -r line; do
            [ -z "$line" ] && continue
            file=$(parse_grep_line "$line")
            if is_allowed "$file"; then
                continue
            fi
            echo "LEAK (known token): $line"
            fail=1
        done <<< "$hits"
    fi
done

# Step 2: HEC-token-shape scan - matches `default_token:` values that look like real tokens.
# Pattern: default_token: followed by a 30+ char base64-url alphabet string.
# Excludes obvious placeholders.
for p in "${PATHS[@]}"; do
    hits=$(grep -rnIE "${EXCLUDE_ARGS[@]}" "default_token:[[:space:]]*['\"]?[A-Za-z0-9_/+=-]{30,}['\"]?" "$p" 2>/dev/null || true)
    if [ -n "$hits" ]; then
        while IFS= read -r line; do
            [ -z "$line" ] && continue
            if echo "$line" | grep -qiE "your-.*-here|placeholder|replace_me|example|dummy|fake|test-token"; then
                continue
            fi
            file=$(parse_grep_line "$line")
            if is_allowed "$file"; then
                continue
            fi
            echo "LEAK (HEC-shape): $line"
            fail=1
        done <<< "$hits"
    fi
done

if [ "$fail" -eq 1 ]; then
    echo ""
    echo "FAILED: one or more secret-leak patterns matched. See lines above."
    echo "If this is a false positive, add the file to ALLOWED_MENTIONS in scripts/check_secret_leaks.sh."
    exit 1
fi

echo "OK: no secret-leak patterns found."
exit 0
