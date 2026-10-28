# Deployment — Zero to End

Complete, ordered guide to deploy the **One Touch Resolve** from an empty
machine to a fully running system. Every step maps to a real file in this repo
(`scripts/`, `infra/`, `.env.example`, `Makefile`).

There are two deployment targets. Do **Path A** first — it proves the whole
journey works with no AWS channel provisioning. Do **Path B** only when you want
live AWS infrastructure and real device channels.

```
Path A  Local / simulation run        — minutes, no channel setup
Path B  Full AWS deployment (CDK)      — infra + AgentCore + live channels
```

---

## 0. Prerequisites

Install and verify these before anything else.

| Requirement | Why | Check |
|---|---|---|
| AWS account + IAM permissions | Bedrock, Lambda, SNS, DynamoDB, SES, S3, IAM, `sms-voice`, `social-messaging` | `aws sts get-caller-identity` |
| AWS CLI v2 (`aws configure`) | all AWS calls | `aws --version` |
| Python 3.11+ | agent, channels, ZCAA server | `python3 --version` |
| Node.js 18+ and AWS CDK v2 | `infra/` deploy | `node -v` · `npx cdk --version` |
| Docker | packaging the AgentCore agent container | `docker --version` |
| Bedrock model access | triage + agent reasoning | enable `amazon.nova-pro-v1:0` (and/or `nova-pro`) in your Region |

```bash
# From the repo root
pip install -r requirements.txt     # boto3, strands-agents, bedrock-agentcore, ...
cd infra && npm install && cd ..    # CDK + TypeScript deps
# or simply:  make install
```

---

## 1. Configure environment

```bash
cp .env.example .env
$EDITOR .env
```

Minimum to start (simulation): leave `SIMULATE_CHANNELS=true`. Set these for any
real sending:

| Key | Needed for | Notes |
|---|---|---|
| `AWS_REGION` | everything | e.g. `us-east-1` |
| `BEDROCK_MODEL_ID` | triage/agent | `amazon.nova-pro-v1:0` (or `nova-pro`) |
| `SES_SENDER_EMAIL` | real email | must be a **verified** SES identity |
| `SIMULATE_CHANNELS` | gate | `true` = log payloads; `false` = real SMS/RCS/WhatsApp |
| `SIMULATE_EMAIL` | gate | `false` = real SES send |
| `EUM_PHONE_POOL_ID` / `EUM_RCS_AGENT_ID` / `EUM_ORIGINATION_IDENTITY` | live SMS/RCS | pool with RCS agent **+ dedicated SMS originator** |
| `WHATSAPP_PHONE_NUMBER_ID` | live WhatsApp | EUM Social origination id |
| `AGENTCORE_RUNTIME_ARN` / `AGENTCORE_MEMORY_ID` | live agent | auto-written by `deploy_agent.sh` |

> Never commit the real `.env`. It is git-ignored.

---

## PATH A — Local / simulation run (do this first)

Proves the full FNOL→settlement journey with no channel provisioning.

### A.1 Run the tests
```bash
make test            # or: python3 -m pytest -q
```
Expected: all tests pass (41 as of this writing).

### A.2 Start the local servers
```bash
./start.sh
```
Starts two processes (PIDs in `logs/`):
- **Phone app** (customer UI) → `http://<host>:8080/`
- **Operator dashboard** → `http://<host>:8081/` (also `:8080/dashboard`)

If `dashboard/dist/` is missing, `start.sh` runs `cd dashboard && npm run build`
automatically.

### A.3 Drive a journey (optional, via API)
```bash
# Start a session
curl -s -X POST http://localhost:8080/api/start -H 'Content-Type: application/json' \
  -d '{"name":"Alex Rivera","policy":"HO-123456","location":"I-5 near Tacoma",
       "vehicle":"2022 Honda Civic","phone":"+15555550100",
       "description":"Rear-ended at a stoplight, bumper damage"}'

# Respond to each prompt with the returned session_id:
curl -s -X POST http://localhost:8080/api/respond -H 'Content-Type: application/json' \
  -d '{"session_id":"<ID>","answer":"Yes, I'\''m safe"}'
```
Watch it live on the dashboard. With `SIMULATE_EMAIL=false` and a verified
`SES_SENDER_EMAIL`, the summary email sends for real; channels stay simulated
while `SIMULATE_CHANNELS=true`.

### A.4 Stop
```bash
./stop.sh
```

---

## PATH B — Full AWS deployment

Provisions the serverless backbone, the AgentCore agent, and (optionally) live
channels. Each sub-step is reversible; see teardown (§B.6).

### B.1 Validate access (non-destructive)
```bash
./scripts/check_prereqs.sh       # or: make prereqs
```
Checks `.env`, AWS credentials, Bedrock reachability, SES identity, and EUM
access. Resolve any `[FAIL]` before continuing. (Simulation works regardless.)

### B.2 Deploy infrastructure (CDK)
```bash
./scripts/deploy.sh              # or: make deploy
```
Runs `npm install`, `cdk bootstrap` (idempotent), `cdk synth`, then
`cdk deploy`. The **`CoordinatedOutcomeEngine`** stack (`infra/lib/coe-stack.ts`)
creates:
- SNS topics: `coe-eum-sms-rcs-inbound`, `coe-eum-social-whatsapp-inbound`
- `coe-dispatcher` Lambda (Python 3.12) + a 14-day DLQ `coe-dispatcher-dlq`
- DynamoDB: `coe-claims` (state) and `coe-dedupe` (idempotency, TTL)
- S3 inbound-media bucket (30-day lifecycle, public access blocked)
- Least-privilege IAM (EUM `sms-voice`, Social `social-messaging`, SES, Bedrock AgentCore, DynamoDB)
- CloudWatch alarms: DLQ-not-empty, dispatcher-errors

**Save the stack outputs** (printed at the end): `SmsRcsInboundTopicArn`,
`WhatsAppInboundTopicArn`, `ClaimsTableName`, `InboundMediaBucketName`,
`DispatcherFunctionName`.

> Validate the template first without deploying: `make synth`.

### B.3 Deploy the agent to Bedrock AgentCore
```bash
./scripts/deploy_agent.sh        # or: make deploy-agent
```
- If the **`agentcore`** starter toolkit is installed: `agentcore configure`
  (entrypoint `agent/runtime.py`) → `agentcore launch`, then it writes
  `AGENTCORE_RUNTIME_ARN` and `AGENTCORE_MEMORY_ID` back into `.env`.
- Otherwise it falls back to the **ECR + Docker** path: builds the image
  (`Dockerfile`), pushes to the `coe-agent` ECR repo, and prints the
  `create-agent-runtime` step to run (console or CLI). Add the resulting ARN to
  `.env`.

### B.4 Propagate the agent ARNs to the Lambda
The dispatcher Lambda reads `AGENTCORE_RUNTIME_ARN` / `AGENTCORE_MEMORY_ID` from
its environment. After B.3 wrote them to `.env`, re-deploy infra so the Lambda
picks them up:
```bash
./scripts/deploy.sh
```

### B.5 Wire live channels (only for real-device demo)
Follow `docs/PREREQUISITES.md` for full detail. Summary:

1. **SMS/RCS** — Create an RCS Agent, obtain a **dedicated** SMS number/sender id,
   put **both in one phone pool** (shared routes are NOT a valid RCS fallback).
   Enable two-way messaging and point the RCS Agent's inbound at
   `SmsRcsInboundTopicArn` (from B.2). Fill `EUM_*` in `.env`.
2. **WhatsApp** — Link a WhatsApp Business Account to EUM Social; set
   `WHATSAPP_PHONE_NUMBER_ID`; point inbound events at `WhatsAppInboundTopicArn`.
3. **SES** — Verify `SES_SENDER_EMAIL`; in the sandbox, also verify recipients or
   request production access.
4. Set `SIMULATE_CHANNELS=false` (the Lambda already sets this in `infra/`), then
   re-run `./scripts/deploy.sh` to push env changes.

### B.6 Teardown (reverse everything)
```bash
cd infra && npx cdk destroy --force && cd ..   # removes the CDK stack + resources
# If an ECR image was pushed:
aws ecr delete-repository --repository-name coe-agent --force --region "$AWS_REGION"
# Delete the AgentCore Runtime + Memory you created in B.3 (console or CLI).
make clean                                      # local build artifacts/caches
```
> `coe-claims`, `coe-dedupe`, the media bucket, and SNS topics are set to
> `RemovalPolicy.DESTROY`, so `cdk destroy` removes them. AgentCore and any
> channel resources (pool, RCS agent, WABA) are created outside CDK — delete
> those manually.

---

## Verification checklist

| Check | Command / signal |
|---|---|
| Tests pass | `make test` → all green |
| Local UIs up | `curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/` → `200` |
| Journey completes | dashboard state reaches `SETTLED` |
| Real email sent | SES send returns a `messageId` (not `simulated`) |
| Infra healthy | CloudWatch alarms `coe-dispatcher-dlq-not-empty` / `coe-dispatcher-errors` not in ALARM |
| Inbound path | publish a test event to the SNS topic → dispatcher invoked, no DLQ growth |

---

## Quick reference (Makefile targets)

```
make install       Install Python + CDK deps
make test          Run unit + e2e tests
make synth         CDK synth (validate infra, no deploy)
make deploy        Deploy AWS infrastructure (CDK)
make deploy-agent  Deploy supervisor to Bedrock AgentCore
make prereqs       Validate .env + AWS access (read-only)
make clean         Remove build artifacts and caches
```

## Troubleshooting

- **`cdk bootstrap` fails** — ensure the Region is bootstrapped and your IAM
  principal can create the CDK toolkit stack; `deploy.sh` runs it idempotently.
- **SES send rejected** — in the sandbox both sender *and* recipient must be
  verified; check the identity is in `Success` state.
- **RCS message fails / no fallback** — the pool lacks a dedicated SMS originator;
  shared routes are not supported for RCS→SMS fallback.
- **Agent ARNs empty in Lambda** — you skipped B.4; re-run `./scripts/deploy.sh`
  after `deploy_agent.sh` wrote them to `.env`.
- **Dashboard 404 "UI not built"** — run `cd dashboard && npm run build` (or just
  re-run `./start.sh`).
