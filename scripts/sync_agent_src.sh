#!/usr/bin/env bash
# Sync the canonical engine source (src/agent, src/channels, src/shared) into the
# AgentCore deployment package as coe_-prefixed packages.
#
# Why: the AgentCore CodeZip build bundles only what lives under
# deployment/coeagent/app/coe_supervisor/. Rather than keep hand-edited copies
# (which drift), we GENERATE them from the single source of truth in src/ and
# rewrite the intra-package imports to the coe_ prefix. The generated packages
# are gitignored; run this before `agentcore deploy`.
#
# Usage:  ./scripts/sync_agent_src.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT/src"
APP="$ROOT/deployment/coeagent/app/coe_supervisor"

echo "==> Syncing src/ -> $APP (coe_ prefixed)"

for pkg in agent channels shared; do
  dest="$APP/coe_$pkg"
  rm -rf "$dest"
  mkdir -p "$dest"
  # Copy only Python sources (skip caches/compiled).
  (cd "$SRC/$pkg" && find . -name '*.py' -not -path '*/__pycache__/*' -print0 \
    | cpio -0pdm "$dest" >/dev/null 2>&1)
done

# Rewrite intra-package imports to the coe_ prefix so the bundled packages resolve.
find "$APP"/coe_agent "$APP"/coe_channels "$APP"/coe_shared -name '*.py' -print0 \
  | while IFS= read -r -d '' f; do
    sed -i -E \
      -e 's/^from shared\b/from coe_shared/' \
      -e 's/^from channels\b/from coe_channels/' \
      -e 's/^from agent\b/from coe_agent/' \
      -e 's/^import shared\b/import coe_shared/' \
      -e 's/^import channels\b/import coe_channels/' \
      -e 's/^import agent\b/import coe_agent/' \
      "$f"
  done

echo "==> Done. Generated: coe_agent, coe_channels, coe_shared"
echo "    (gitignored build artifacts — regenerate anytime with this script)"
