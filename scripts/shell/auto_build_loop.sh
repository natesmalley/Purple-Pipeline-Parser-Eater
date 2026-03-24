#!/bin/bash
for i in {8..30}; do
  echo "BUILD ATTEMPT $i"
  docker-compose build parser-eater > build_attempt_${i}.log 2>&1
  if [ $? -eq 0 ]; then
    echo "SUCCESS - Docker image built!"
    exit 0
  fi
  hash=$(grep -A 20 "ERROR: Hashes are required" build_attempt_${i}.log | grep "nvidia-\|triton" | head -1 | awk '{print $1 " " $2}')
  if [ -z "$hash" ]; then
    echo "BUILD FAILED - No more hashes to add"
    tail -50 build_attempt_${i}.log
    exit 1
  fi
  echo "Adding hash: $hash"
  package=$(echo "$hash" | cut -d'=' -f1)
  version=$(echo "$hash" | awk -F'==' '{print $2}' | awk '{print $1}')
  hashval=$(grep "$package==$version" build_attempt_${i}.log | grep "hash=sha256" | head -1 | sed 's/.*\(--hash=sha256:[a-f0-9]*\).*/\1/')
  if [ -n "$hashval" ]; then
    sed -i "/^tqdm==/i ${package}==${version} \\\n    ${hashval}\n    # via torch (transitive dependency - pinned for hash verification)" requirements.txt
    echo "Added $package==$version"
  fi
done
