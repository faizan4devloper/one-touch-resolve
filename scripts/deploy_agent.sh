#!/usr/bin/env bash
# Build and deploy the supervisor agent container to Amazon Bedrock AgentCore Runtime.
#
# This uses the AgentCore starter toolkit if available; otherwise it prints the
# manual ECR build/push + create-agent-runtime steps. Writes AGENTCORE_RUNTIME_ARN
# and AGENTCORE_MEMORY_ID back into .env on success.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

REGION="${AWS_REGION:-us-east-1}"
REPO="coe-agent"
IMAGE_TAG="latest"

echo "==> Region: $REGION"

# Upsert KEY=VALUE into .env (idempotent). Keeps the deploy handoff seamless so
# the dispatcher Lambda picks up AGENTCORE_RUNTIME_ARN / AGENTCORE_MEMORY_ID on
# the next `cdk deploy` without a manual edit.
upsert_env() {
  local key="$1" value="$2" file="$ROOT/.env"
  [ -f "$file" ] || touch "$file"
  if grep -qE "^${key}=" "$file"; then
    # portable in-place edit (GNU + BSD sed)
    sed -i.bak "s|^${key}=.*|${key}=${value}|" "$file" && rm -f "$file.bak"
  else
    printf '%s=%s\n' "$key" "$value" >> "$file"
  fi
  echo "==> wrote ${key} to .env"
}

if command -v agentcore >/dev/null 2>&1; then
  echo "==> Using AgentCore starter toolkit"
  agentcore configure --entrypoint agent/runtime.py --name coe-supervisor || true
  agentcore launch | tee /tmp/agentcore_launch.out || true
  # Best-effort: capture the Runtime ARN and Memory id from the toolkit output
  # and persist them so the infra + Lambda are wired automatically.
  RUNTIME_ARN="$(grep -oE 'arn:aws:bedrock-agentcore:[^ "]*runtime/[^ "]*' /tmp/agentcore_launch.out | head -1 || true)"
  MEMORY_ID="$(grep -oE '[Mm]emory[ _-]?[Ii][Dd]["'"'"':= ]+[A-Za-z0-9_-]+' /tmp/agentcore_launch.out | grep -oE '[A-Za-z0-9_-]+$' | head -1 || true)"
  [ -n "${RUNTIME_ARN:-}" ] && upsert_env "AGENTCORE_RUNTIME_ARN" "$RUNTIME_ARN"
  [ -n "${MEMORY_ID:-}" ] && upsert_env "AGENTCORE_MEMORY_ID" "$MEMORY_ID"
  echo "==> Agent launched. ARNs (if detected) written to .env — re-run ./scripts/deploy.sh to propagate to the Lambda."
  exit 0
fi

echo "==> AgentCore toolkit not found; using ECR + Docker path"
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
ECR="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

aws ecr describe-repositories --repository-names "$REPO" --region "$REGION" >/dev/null 2>&1 \
  || aws ecr create-repository --repository-name "$REPO" --region "$REGION" >/dev/null

aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$ECR"

echo "==> Building image"
docker build -t "${REPO}:${IMAGE_TAG}" .
docker tag "${REPO}:${IMAGE_TAG}" "${ECR}/${REPO}:${IMAGE_TAG}"

echo "==> Pushing image"
docker push "${ECR}/${REPO}:${IMAGE_TAG}"

cat <<EOF

Image pushed: ${ECR}/${REPO}:${IMAGE_TAG}

Next, create the AgentCore Runtime pointing at this image (console or CLI), then
add the resulting ARN to .env:

  AGENTCORE_RUNTIME_ARN=arn:aws:bedrock-agentcore:${REGION}:${ACCOUNT_ID}:runtime/coe-supervisor

EOF
