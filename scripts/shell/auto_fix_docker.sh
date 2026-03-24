#!/bin/bash
# Automated Docker build fix loop
# Runs builds continuously until success, extracting and adding missing hashes
# Maintains full STIG compliance and hash-pinning security

MAX_ATTEMPTS=30
attempt=1

echo "AUTOMATED DOCKER BUILD FIX LOOP"
echo "Will run up to $MAX_ATTEMPTS attempts"
echo ""

while [ $attempt -le $MAX_ATTEMPTS ]; do
    echo "================================================================================"
    echo "BUILD ATTEMPT $attempt/$MAX_ATTEMPTS"
    echo "================================================================================"

    # Run docker build
    docker-compose build parser-eater > build_attempt_${attempt}.log 2>&1
    exit_code=$?

    if [ $exit_code -eq 0 ]; then
        echo ""
        echo "================================================================================"
        echo "DOCKER BUILD SUCCESSFUL!"
        echo "================================================================================"
        echo "Image: purple-pipeline-parser-eater:9.0.0"
        echo "All security hardening intact"
        echo ""
        echo "Next: docker-compose up -d && docker-compose exec parser-eater python main.py --verbose"
        exit 0
    fi

    # Extract missing hashes
    missing=$(grep -A 50 "ERROR: Hashes are required" build_attempt_${attempt}.log | grep -E "^\s+(nvidia-|triton|sympy-mpmath).+--hash=sha256:" | head -20)

    if [ -z "$missing" ]; then
        echo "BUILD FAILED - Not a hash issue or no more hashes to add"
        echo "Check build_attempt_${attempt}.log for details"
        tail -50 build_attempt_${attempt}.log
        exit 1
    fi

    echo "Found missing hashes:"
    echo "$missing"
    echo ""
    echo "Adding to requirements.txt..."

    # Add hashes before tqdm line
    # Extract just the package lines and format them
    while IFS= read -r line; do
        # Clean up the line and add proper formatting
        clean_line=$(echo "$line" | sed 's/^\s*//')
        package=$(echo "$clean_line" | awk '{print $1}')
        hash=$(echo "$clean_line" | grep -o 'hash=sha256:[a-f0-9]*')

        if [ -n "$package" ] && [ -n "$hash" ]; then
            # Insert before tqdm
            sed -i "/^tqdm==/i ${package} \\\\\n    --${hash}\n    # via torch (transitive dependency - pinned for hash verification)" requirements.txt
            echo "  Added: $package"
        fi
    done <<< "$missing"

    attempt=$((attempt + 1))
    echo ""
    echo "Retrying build..."
    sleep 2
done

echo "Max attempts reached without success"
exit 1
