#!/usr/bin/env bash
# Start the One Touch Resolve app as two servers:
#   :8080  — ZCAA API + customer phone app  (python3 -m zcaa.api)
#   :8081  — operator dashboard (static dist/, served by serve.mjs)
#
# The dashboard server reverse-proxies /api -> the API port, so the browser
# only needs the single dashboard port (works behind the Cloud9 preview proxy).
# Logs: logs/api.log, logs/dashboard.log.  Stop with ./stop.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

API_PORT="${API_PORT:-8080}"
DASH_PORT="${DASH_PORT:-8081}"

mkdir -p logs

# Load .env so Bedrock/SES config is available to the API process.
if [ -f .env ]; then set -a; . ./.env; set +a; fi

# Build the dashboard if dist/ is missing.
if [ ! -f ui/dist/index.html ]; then
  echo "==> Building dashboard (dist/ missing)"
  (cd ui && npm run build)
fi

echo "==> Starting API + phone app on :$API_PORT"
nohup python3 -m zcaa.api "$API_PORT" > logs/api.log 2>&1 &
echo $! > logs/api.pid

echo "==> Starting dashboard on :$DASH_PORT"
nohup node ui/serve.mjs "$DASH_PORT" ui/dist "$API_PORT" > logs/dashboard.log 2>&1 &
echo $! > logs/dashboard.pid

sleep 1
echo
echo "Phone app  : http://<host>:$API_PORT/"
echo "Dashboard  : http://<host>:$DASH_PORT/"
echo "Logs       : logs/api.log, logs/dashboard.log"
echo "Stop       : ./stop.sh"
