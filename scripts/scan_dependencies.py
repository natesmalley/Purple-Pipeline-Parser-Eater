#!/usr/bin/env python3
"""
Dependency Vulnerability Scanner

Scans requirements.txt for known vulnerabilities.
"""

import subprocess
import sys
import json
import os
from pathlib import Path


def scan_with_pip_audit():
    """Scan using pip-audit"""
    try:
        # Check if requirements.txt exists
        if not Path('requirements.txt').exists():
            print("ERROR: requirements.txt not found")
            return False

        result = subprocess.run(
            ['pip-audit', '--requirement', 'requirements.txt', '--format', 'json'],
            capture_output=True,
            text=True,
            check=False
        )

        if result.returncode not in [0, 1]:
            print("ERROR: pip-audit failed")
            print(result.stderr)
            return False

        # pip-audit returns JSON output
        try:
            output = result.stdout.strip()
            if not output:
                print("✓ No vulnerabilities found")
                return True

            vulnerabilities = json.loads(output)

            if vulnerabilities.get('vulnerabilities'):
                print(f"Found {len(vulnerabilities['vulnerabilities'])} vulnerabilities:")
                for vuln in vulnerabilities['vulnerabilities']:
                    print(f"  - {vuln['name']}: {vuln.get('id', 'Unknown')}")
                return False

            print("✓ No vulnerabilities found")
            return True
        except json.JSONDecodeError:
            # If JSON parsing fails, check return code
            if result.returncode == 0:
                print("✓ No vulnerabilities found")
                return True
            else:
                print("ERROR: Could not parse pip-audit output")
                print(result.stdout)
                return False

    except FileNotFoundError:
        print("ERROR: pip-audit not installed")
        print("Install with: pip install pip-audit")
        return False


def scan_with_safety():
    """Scan using safety"""
    try:
        # Check if requirements.txt exists
        if not Path('requirements.txt').exists():
            print("ERROR: requirements.txt not found")
            return False

        result = subprocess.run(
            ['safety', 'check', '--json', '--file', 'requirements.txt'],
            capture_output=True,
            text=True,
            check=False
        )

        try:
            vulnerabilities = json.loads(result.stdout)
            if vulnerabilities and isinstance(vulnerabilities, list) and len(vulnerabilities) > 0:
                print(f"Found {len(vulnerabilities)} vulnerabilities:")
                for vuln in vulnerabilities:
                    print(f"  - {vuln.get('name', 'Unknown')}: {vuln.get('vulnerability', 'Unknown')}")
                return False
        except json.JSONDecodeError:
            if result.returncode == 0:
                print("✓ No vulnerabilities found")
                return True

        print("✓ No vulnerabilities found")
        return True

    except FileNotFoundError:
        print("ERROR: safety not installed")
        print("Install with: pip install safety")
        return False


def main():
    """Main scanning function"""
    print("Scanning dependencies for vulnerabilities...")
    print("=" * 50)

    # Try pip-audit first
    success = scan_with_pip_audit()

    # If pip-audit is not available, try safety as fallback
    if not success:
        try:
            result = subprocess.run(['pip-audit', '--version'], capture_output=True)
            if result.returncode != 0:
                print("\nTrying safety as fallback...")
                success = scan_with_safety()
        except FileNotFoundError:
            print("\nTrying safety as fallback...")
            success = scan_with_safety()

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
