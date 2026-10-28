#!/usr/bin/env bash
# Stop the One Touch Resolve app servers started by ./start.sh
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

for name in api dashboard; do
  pidf="logs/$name.pid"
  if [ -f "$pidf" ]; then
    pid="$(cat "$pidf")"
    if kill "$pid" 2>/dev/null; then echo "stopped $name (pid $pid)"; fi
    rm -f "$pidf"
  fi
done

# Belt-and-suspenders: kill any stragglers by command signature.
pkill -f "zcaa.api" 2>/dev/null && echo "killed stray zcaa.api" || true
pkill -f "serve.mjs" 2>/dev/null && echo "killed stray serve.mjs" || true
