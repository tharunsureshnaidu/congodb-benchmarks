#!/usr/bin/env bash
# One command: prepare the dataset, benchmark every configured platform, merge results.
# Usage: scripts/run_all.sh [platform ...]   (defaults to all 5)
set -euo pipefail
cd "$(dirname "$0")/.."

if [ "$#" -eq 0 ]; then
  PLATFORMS=(cognodb aura memgraph falkordb arango)
else
  PLATFORMS=("$@")
fi

python -m benchmarks.dataset

for platform in "${PLATFORMS[@]}"; do
  echo "=== $platform ==="
  python -m benchmarks.run_benchmark --platform "$platform"
done

python -m benchmarks.merge_results
