#!/usr/bin/env bash
# Deploy the One Touch Resolve infrastructure via AWS CDK.
# Provisions: SNS topics, Dispatcher Lambda (+DLQ), DynamoDB tables, S3, IAM.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/infra"

# Load .env if present so origination identities flow into the Lambda env.
if [[ -f "$ROOT/.env" ]]; then
  set -a; # shellcheck disable=SC1090
  source "$ROOT/.env"; set +a
fi

echo "==> Installing CDK dependencies"
npm install --silent

echo "==> Bootstrapping (idempotent)"
npx cdk bootstrap >/dev/null 2>&1 || true

echo "==> Synthesizing"
npx cdk synth >/dev/null

echo "==> Deploying CoordinatedOutcomeEngine stack"
npx cdk deploy --require-approval never

echo ""
echo "Done. Next: point your EUM RCS Agent + WhatsApp inbound at the SNS topic"
echo "ARNs shown above, then run ./scripts/deploy_agent.sh to deploy the agent."
