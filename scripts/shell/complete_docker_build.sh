#!/bin/bash
attempt=1
max_attempts=50
while [ $attempt -le $max_attempts ]; do
  docker-compose build parser-eater > build_final_${attempt}.log 2>&1
  if [ $? -eq 0 ]; then
    echo "SUCCESS - Docker image built at attempt $attempt!"
    docker images | grep purple-pipeline-parser-eater
    exit 0
  fi
  missing=$(grep -A 50 "ERROR: Hashes are required" build_final_${attempt}.log | grep -E "^\s*(nvidia-|triton|nvjitlink).+--hash=sha256:" | head -1)
  if [ -z "$missing" ]; then
    exit 1
  fi
  pkg=$(echo "$missing" | awk '{print $1}')
  hash=$(echo "$missing" | grep -o 'hash=sha256:[a-f0-9]*')
  if [ -n "$pkg" ] && [ -n "$hash" ]; then
    sed -i "/^tqdm==/i ${pkg} \\\n    --${hash}\n    # via torch (transitive dependency - pinned for hash verification)" requirements.txt
  fi
  attempt=$((attempt + 1))
done
exit 1
