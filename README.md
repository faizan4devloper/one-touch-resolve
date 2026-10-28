# One Touch Resolve — Insurance Claims Coordination Agent

> An agentic, omnichannel customer-engagement solution built on **AWS Communication Developer Services (CDS)** — AWS End User Messaging (SMS/RCS), AWS End User Messaging Social (WhatsApp), and Amazon SES — orchestrated by **Amazon Bedrock AgentCore**.
>
> Submission for the **AWS CDS Agentic AI Partner Hackathon (Sept. 2026)**.

---

## The problem

Property insurance claims now take **40.7 days on average** from First Notice of Loss (FNOL) to final payment — **among the longest since J.D. Power began tracking in 2008** (J.D. Power 2026 U.S. Property Claims Satisfaction Study; repair cycle alone averages 29.6 days). Policyholders expect resolution in **~11 days**; digital-first carriers already close in **~15 days**.

The delay is rarely the adjuster. It is **fragmentation**: the policyholder, adjuster, repair shop, parts supplier, and lienholder each live in a different system and communicate on a different channel. Nobody owns the *coordination*.

## The solution

The **One Touch Resolve** is a domain-agnostic orchestration pattern, instantiated here as an **Insurance Claims Coordination Agent**. A **supervisor agent** on Amazon Bedrock AgentCore drives multiple **independent external parties** — each on the channel chosen for a real reason — to a completed outcome, with **one shared claim state** that follows the participant across **RCS → SMS → WhatsApp → email**.

Three differentiators that a single-agent chatbot cannot fake:

1. **Multi-party commit gate.** The supervisor spawns specialist sub-agents (one per party) and *blocks advancing the claim state until all required parties commit*. It reconciles conflicting/late replies and re-plans when any party fails.
2. **Channel-aware continuity.** Using AWS EUM native RCS→SMS fallback (dedicated originator in a phone pool), the engine *detects silent channel degradation and continues the same workflow on SMS with preserved state*, backed by AgentCore Memory as the single cross-channel session store.
3. **Human-in-the-loop approval before money moves.** When the commit gate opens, the claim enters a `PENDING_APPROVAL` state and the adjuster gets an interactive **RCS Approve/Hold card**; `issue_settlement` *refuses to run* until a human records an `approved` decision — enforced in the state machine and in code, not in prompt text. The agent coordinates; the human authorizes the payout.

Plus a **multimodal FNOL**: the policyholder sends a real damage **photo** on WhatsApp and **Amazon Bedrock Nova Pro vision** assesses it live — severity, drivability, and a one-line reason drawn from the image — and that assessment drives the branch (severe/not-drivable → tow; minor/drivable → repair). Not a scripted outcome: the journey follows what the model actually sees.

## Which AWS CDS services are used

| Service | Role in the solution |
|---|---|
| **Amazon SES** | **Live at runtime** — durable, auditable documents: settlement letter + claim summary email. |
| **AWS End User Messaging — SMS** | **Live at runtime** via a provisioned SMS **simulator number** (zero carrier registration): the engine's own adapter calls the real `SendTextMessage` API and AWS returns a MessageId with real delivery events + CloudWatch metrics. Run `python3 scripts/send_live_cds.py` to reproduce. |
| **AWS End User Messaging — RCS** | Verified-sender interactive cards (appointment cards, choices). Adapter implemented + service-model-validated; add an RCS test agent (≈5 min, no carrier approval) to light it up on a registered device. |
| **WhatsApp (Meta Cloud API)** | Rich-media two-way dialog + multimodal FNOL with the policyholder. Runs on the **Meta WhatsApp Cloud API (Graph API)** — AWS EUM Social WABA onboarding was blocked in our account. *(Eligible for the Meta "Best of WhatsApp" prize.)* |

> **Live-CDS proof:** `scripts/send_live_cds.py` fires a real SES email and a real EUM SMS through the
> repo's own `channels/` adapters and prints the AWS-returned MessageIds — reproducible runtime evidence
> that two AWS CDS services are exercised live, end to end, through the codebase.

Agentic layer: **Amazon Bedrock AgentCore** (Runtime + Memory + multi-agent collaboration) with the **Strands Agents SDK**, using **Amazon Nova Pro** for tool-calling and **Nova Pro vision** for real damage-photo triage at FNOL.

## Architecture

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full diagram and data flow.

```
Customer / Repair shop / Lienholder devices
        │  (WhatsApp · RCS · SMS inbound)
        ▼
AWS End User Messaging  +  EUM Social  ──►  Amazon SNS topic
                                                │
                                                ▼
                                        Dispatcher Lambda
                                                │ invokes
                                                ▼
                        Bedrock AgentCore Runtime — Supervisor (Strands, Nova Pro)
                          ├─ AgentCore Memory (one claim state, keyed by actor_id)
                          ├─ Specialist sub-agents: Claimant · RepairShop · Parts · Lienholder
                          └─ Tools (Lambda): open_claim, request_estimate, check_parts,
                                             notify_lienholder, commit_gate, send_message
                                                │
              ┌─────────────────────────────────┼──────────────────────────────────┐
              ▼                                  ▼                                   ▼
        SendTextMessage                    WhatsApp send                       Amazon SES
        (RCS → SMS fallback, pool)         (EUM Social)                        (email documents)
                                                │
                                                ▼
                                    Amazon DynamoDB  (cross-channel claim state)
```

## Repository layout

```
coordinated-outcome-engine/
├── src/                     # Engine source — single source of truth
│   ├── agent/               #   Strands supervisor, sub-agents, commit gate, approval gate, memory, safety, tools/
│   ├── channels/            #   AWS CDS channel adapters (RCS/SMS, WhatsApp, SES) + dispatcher/router
│   └── shared/              #   Claim models, resilient store (DynamoDB + in-process fallback), dedupe
├── deployment/              # Amazon Bedrock AgentCore deployment (new @aws/agentcore CLI project)
│   └── coeagent/            #   app/coe_supervisor (runtime entrypoint), agentcore.json, cdk/
├── infra/                   # AWS CDK (TypeScript) — SNS, Lambdas, DynamoDB, IAM, SES
├── ui/                      # React/Vite operator dashboard (Mission Control) + customer phone app
├── zcaa/                    # "Zero-Call Accident Assist" — local demo API (stdlib) serving the UI + JSON/SSE
├── seed/                    # Demo data (policies, personas, scenario script)
├── scripts/                 # deploy, sync_agent_src, measure_e2e, prereqs helpers
├── tests/                   # Unit + integration tests (48, all passing)
└── docs/                    # Architecture, demo script, pitch deck, submission text
```

> **Note on `deployment/`:** the AgentCore CodeZip bundles only what lives under
> `app/coe_supervisor/`. The `coe_agent` / `coe_channels` / `coe_shared` packages
> there are **generated from `src/`** by `scripts/sync_agent_src.sh` (and gitignored).
> `src/` stays the single source of truth — never edit the generated copies.

## Deployment status

The supervisor is **deployed and verified live** on Amazon Bedrock AgentCore Runtime
(`us-east-1`): Strands + Amazon Nova Pro, 12 coordination tools, 4 specialist
sub-agents, with **AgentCore Memory** (short + long term) backing cross-channel
continuity. Claim state uses DynamoDB when the runtime role is authorized, and
transparently falls back to an in-process store otherwise (`COE_STORE_BACKEND`).

## Quick start

Prerequisites and channel setup are documented in [`docs/PREREQUISITES.md`](docs/PREREQUISITES.md).

### Run the offline demo (no AWS required)

```bash
# Timed FNOL -> settlement journey across 4 parties / 3 channels, fully simulated.
make demo          # == SIMULATE_CHANNELS=true python scripts/measure_e2e.py
make test          # run the 48 unit/integration tests
```

### Run the local UI + API

```bash
cp .env.example .env && $EDITOR .env   # configure region, SES sender, demo contacts
./start.sh                             # :8080 ZCAA API + phone app · :8081 operator dashboard
./stop.sh
```

### Deploy to AWS

```bash
# 1. Infrastructure (SNS, Lambdas, DynamoDB, IAM, SES) via CDK
cd infra && npm install && npx cdk deploy && cd ..

# 2. Supervisor agent -> Amazon Bedrock AgentCore Runtime (new @aws/agentcore CLI)
./scripts/sync_agent_src.sh                       # regenerate bundled packages from src/
cd deployment/coeagent && agentcore deploy --yes  # ECR/IAM/Runtime/Memory via CDK
```

For a live channel demo you need a dedicated originator in a phone pool (RCS→SMS fallback requires it — shared routes are **not** supported). See prerequisites.

## Cross-industry framing (repeatable offering)

The same engine re-skins across verticals by swapping only the **sub-agent roster**, the **commit-gate rules**, and the **document templates** — the orchestration core, channel-routing layer, and cross-channel memory stay constant:

| Vertical | Parties coordinated |
|---|---|
| **Insurance** (this build) | policyholder · adjuster · repair shop · parts supplier · lienholder |
| Utilities | customer · field crew · caregiver · backup facility |
| Retail / logistics | customer · courier · warehouse · installer |
| Healthcare (scheduling only) | patient · clinic · payer · specialist |
| B2B finance | buyer AP · seller AR · POD record · ERP |

Ship the engine once; sell a configured "Coordination Agent" per vertical on AWS Marketplace.

## License

MIT — see [`LICENSE`](LICENSE).

## Disclaimer

This is a hackathon reference implementation. Statistics are cited from public industry/analyst sources (J.D. Power 2026, and others listed in `docs/ARCHITECTURE.md`). Insurance logic is illustrative and not a substitute for a licensed carrier's claims process.
