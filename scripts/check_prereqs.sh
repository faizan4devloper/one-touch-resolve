#!/usr/bin/env bash
# Validate .env and AWS access for each service the engine uses.
# Non-destructive: only performs read/describe calls.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PASS=0; FAIL=0
ok()   { echo "  [ OK ] $1"; PASS=$((PASS+1)); }
bad()  { echo "  [FAIL] $1"; FAIL=$((FAIL+1)); }

echo "==> Checking .env"
if [[ -f .env ]]; then
  set -a; source .env; set +a
  ok ".env present"
else
  bad ".env missing (cp .env.example .env)"
fi

echo "==> Checking AWS credentials"
if aws sts get-caller-identity >/dev/null 2>&1; then
  ok "AWS credentials valid ($(aws sts get-caller-identity --query Account --output text))"
else
  bad "AWS credentials not configured"
fi

REGION="${AWS_REGION:-us-east-1}"

echo "==> Checking Bedrock model access ($BEDROCK_MODEL_ID)"
if aws bedrock list-foundation-models --region "$REGION" \
     --query "modelSummaries[?contains(modelId, 'nova-pro')]" --output text >/dev/null 2>&1; then
  ok "Bedrock reachable"
else
  bad "Cannot list Bedrock models in $REGION"
fi

echo "==> Checking SES sender identity ($SES_SENDER_EMAIL)"
if aws ses get-identity-verification-attributes --identities "$SES_SENDER_EMAIL" \
     --region "$REGION" >/dev/null 2>&1; then
  ok "SES reachable (verify $SES_SENDER_EMAIL is in 'Success' state)"
else
  bad "SES check failed"
fi

echo "==> Checking EUM (sms-voice) access"
if aws pinpoint-sms-voice-v2 describe-phone-numbers --region "$REGION" >/dev/null 2>&1; then
  ok "EUM SMS/RCS reachable"
else
  bad "EUM (pinpoint-sms-voice-v2) not reachable"
fi

echo ""
echo "Summary: $PASS passed, $FAIL failed"
[[ $FAIL -eq 0 ]] && echo "All prerequisites look good." || echo "Resolve the failures above before a live demo. (SIMULATE_CHANNELS=true works regardless.)"
