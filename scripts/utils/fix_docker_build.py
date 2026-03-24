"""
Automated Docker Build Fix Script
Iteratively fixes requirements.txt hash-pinning issues for torch CUDA dependencies
Maintains full STIG compliance and security hash-pinning
"""

import subprocess
import re
import sys
import time

def run_docker_build():
    """Run docker-compose build and capture output - NO FANCY OUTPUT"""
    print("Starting build...")

    result = subprocess.run(
        ["docker-compose", "build", "parser-eater"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )

    # Decode output, ignoring problematic characters
    output = result.stdout.decode('utf-8', errors='ignore')
    return result.returncode, output.split('\n')

def extract_missing_hashes(output_lines):
    """Extract missing hash requirements from build output"""
    missing = []
    capture = False

    for line in output_lines:
        if "ERROR: Hashes are required" in line:
            capture = True
            continue

        if capture and "--hash=sha256:" in line:
            # Extract package==version --hash=sha256:HASH
            match = re.search(r'([\w-]+==[\d.]+)\s+--hash=(sha256:\w+)', line)
            if match:
                package = match.group(1)
                hash_value = match.group(2)
                missing.append((package, hash_value))

        if capture and "[notice]" in line:
            break

    return missing

def add_hashes_to_requirements(missing_hashes):
    """Add missing hashes to requirements.txt"""
    if not missing_hashes:
        return False

    print(f"Found {len(missing_hashes)} missing hash(es)")
    for package, hash_value in missing_hashes:
        print(f"  {package}")

    # Read current requirements.txt
    with open("requirements.txt", "r", encoding='utf-8') as f:
        content = f.read()

    # Find insertion point (before tqdm)
    tqdm_pattern = r'(tqdm==[\d.]+\s+\\)'

    # Build new entries
    new_entries = []
    for package, hash_value in missing_hashes:
        entry = f"{package} \\\n    --{hash_value}\n    # via torch (transitive dependency - pinned for hash verification)\n"
        new_entries.append(entry)

    # Insert before tqdm
    insertion_text = "".join(new_entries)
    new_content = re.sub(tqdm_pattern, insertion_text + r'\1', content, count=1)

    # Write back
    with open("requirements.txt", "w", encoding='utf-8') as f:
        f.write(new_content)

    print(f"Added {len(missing_hashes)} hash(es) to requirements.txt")
    return True

def main():
    """Main execution loop"""
    print("AUTOMATED DOCKER BUILD FIX")
    print("Maintaining full STIG compliance and hash-pinning security")

    max_attempts = 20
    attempt = 1

    while attempt <= max_attempts:
        print(f"\nBUILD ATTEMPT {attempt}/{max_attempts}")

        # Run docker build
        returncode, output_lines = run_docker_build()

        if returncode == 0:
            print("\nDOCKER BUILD SUCCESSFUL")
            print("Image: purple-pipeline-parser-eater:9.0.0")
            return 0

        # Build failed - check if it's a hash issue
        missing_hashes = extract_missing_hashes(output_lines)

        if not missing_hashes:
            print("\nBUILD FAILED - Not a hash issue")
            print("Last 30 lines:")
            for line in output_lines[-30:]:
                print(line.rstrip())
            return 1

        # Add missing hashes and retry
        add_hashes_to_requirements(missing_hashes)

        attempt += 1
        time.sleep(1)

    print(f"\nMaximum attempts ({max_attempts}) reached")
    return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
