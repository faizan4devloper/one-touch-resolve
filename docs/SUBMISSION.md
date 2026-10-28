# Submission — One Touch Resolve (Insurance Claims Coordination Agent)

**Hackathon:** AWS Communication Developer Services (CDS) Agentic AI Partner Hackathon — Sept. 2026
**Repository:** _(add your GitHub/GitLab URL)_
**Deployed project / how to interact:** _(add URL or interaction instructions)_
**ACE Opportunity ID:** **O24826235** (AWS Partner Central · Marketing Campaign code "AWS CDS Agentic AI Hackathon - Sept. 2026")

---

## Inspiration / problem

Property insurance claims take **40.7 days on average** from First Notice of Loss (FNOL) to final
payment — **among the longest since J.D. Power began tracking in 2008** (J.D. Power 2026 U.S. Property
Claims Satisfaction Study; the repair cycle alone averages 29.6 days). Policyholders expect resolution in
**~11 days**; digital-first carriers already close in **~15 days**.

The bottleneck is rarely the adjuster. It is **fragmentation**: the policyholder, adjuster, repair shop,
parts supplier, and lienholder each live in a different system and communicate on a different channel, and
**nobody owns the coordination**.

## What it does

The **One Touch Resolve** is an agentic omnichannel orchestrator. A supervisor agent on **Amazon
Bedrock AgentCore** drives multiple **independent external parties** — each on the AWS CDS channel chosen
for a real reason — to move a claim from FNOL to settlement, with **one shared claim state** that follows
each participant across **WhatsApp → RCS → SMS → email**.

Three differentiators a single-agent chatbot cannot reproduce:

1. **Multi-party commit gate.** Specialist sub-agents each own one party; the claim never advances to a
   committing step until *every required party has committed*. A blocked party (e.g. a back-ordered part)
   forces the supervisor to **re-plan** (arrange a rental, update the timeline) rather than stall.
2. **Channel-aware continuity.** Using AWS End User Messaging's native RCS→SMS fallback (dedicated
   originator in a phone pool), the engine **continues the same workflow on SMS when RCS degrades, with
   preserved state** — because state lives in AgentCore Memory + DynamoDB, never in the transport.
3. **Human-in-the-loop approval before money moves.** Once the commit gate opens, the claim enters a
   `PENDING_APPROVAL` state and the supervisor sends the **adjuster an interactive RCS Approve/Hold card**.
   `issue_settlement` **refuses to run** unless a human has recorded an `approved` decision — enforced in
   the state machine (SETTLED is only reachable from PENDING_APPROVAL) *and* in code, not in prompt text.
   A `held`/`denied` decision kicks the claim back for re-work. This is the governance guarantee every
   2026 claims-AI source (IBM, Camunda, Lorikeet) calls indispensable: the agent coordinates, the human
   authorizes the payout.

## How we built it

- **Agentic layer:** Amazon Bedrock AgentCore (Runtime + Memory + multi-agent collaboration) with the
  Strands Agents SDK and Amazon Nova Pro for fast, low-cost tool-calling.
- **Channels:**
  - Amazon **SES** — **live at runtime**: durable, auditable documents (settlement + summary email).
  - AWS End User Messaging **SMS** — **live at runtime** via a provisioned SMS **simulator number**
    (zero carrier registration, per the hackathon FAQ): the engine's own adapter calls the real
    `SendTextMessage` API and AWS returns a MessageId with real delivery events + CloudWatch metrics.
  - AWS End User Messaging **RCS** — adapter implemented + service-model-validated; add an RCS test
    agent (≈5 min, no carrier approval) to light it up on a registered test device.
  - **WhatsApp** via the **Meta WhatsApp Cloud API** (Graph API), used for multimodal FNOL + proactive
    updates (AWS EUM Social WABA onboarding was blocked in our account; see the WhatsApp note below).
- **Backbone:** inbound → Amazon SNS → Dispatcher Lambda → AgentCore Runtime → tool Lambdas →
  Amazon DynamoDB (claim + party state) → outbound channels. One-command **AWS CDK** deploy.

See `docs/ARCHITECTURE.md` for the full diagram and data flow.

## How AWS CDS is used (and how WhatsApp works)

**Two AWS Communication Developer Services are wired live at runtime** in this build — **Amazon SES**
and **AWS End User Messaging (SMS)** — and both are reproducibly provable through the engine's own
channel adapters (not the raw AWS CLI):

```bash
python3 scripts/send_live_cds.py      # fires real SES + real EUM SMS via channels/*, prints MessageIds
```

Example (account 040504913362, us-east-1):

| CDS service | Adapter | Proof (AWS-returned MessageId) |
|---|---|---|
| Amazon SES | `channels/ses_email.py::send_email` | `010001a180324c34-559c080c-…` |
| AWS End User Messaging (SMS) | `channels/eum_messaging.py::send_text` → `SendTextMessage` | `ae19f518-2469-482a-8afd-18e31d8a4743` |

SES sends settlement/summary email through the real SES API (`SIMULATE_EMAIL=false`, sandbox-verified
sender). EUM SMS sends through a provisioned **SMS simulator number** (`+17015550869`,
`EUM_ORIGINATION_IDENTITY=phone-94adfae3889c40479628703a5ec94018`): the simulator exercises the full
`SendTextMessage` send/receive flow with real event records, delivery receipts, and CloudWatch metrics —
with **no 10DLC / carrier registration** (the hackathon-recommended demo path). The EUM **RCS** adapter is
implemented and validated against the botocore service model (`tests/test_cds_payloads.py`); adding an RCS
test agent (≈5 min, no carrier approval) lights it up on a registered device.

**WhatsApp — honest note for the Meta "Best of WhatsApp" prize.** We attempted AWS End User Messaging
Social, but WABA onboarding was blocked in our account (and Lambda Function URLs are denied by an org SCP).
So WhatsApp runs on the **Meta WhatsApp Cloud API (Graph API)** directly (`channels/whatsapp.py` →
`graph.facebook.com/{version}/{phone_number_id}/messages`), with an inbound webhook Lambda on a separate
account. The adapter is drop-in compatible: set `WHATSAPP_ACCESS_TOKEN` + `WHATSAPP_PHONE_NUMBER_ID` and
`SIMULATE_WHATSAPP=false` to send real messages; it simulates gracefully otherwise.

WhatsApp is the **primary policyholder channel** and is essential, not decorative:

- **Multimodal FNOL (real):** the policyholder sends a damage **photo**; **Amazon Bedrock Nova Pro vision**
  analyzes the actual image and returns a dynamic severity/drivable/reasoning assessment
  (`agent/bedrock.py::triage_fnol_vision`, `POST /api/upload`). The real assessment drives the branch —
  severe/not-drivable dispatches a tow; minor/drivable books a repair.
- **Two-way, contextual dialog:** the claimant taps to consent and receives **proactive updates** on the
  same thread; agent messages are sent to the customer's WhatsApp in real time.
- **Settlement notification + summary** land on WhatsApp and by email (SES).

## Value / impact (measurable)

- Targets the **40.7-day → ~15-day** cycle-time gap (industry vs digital-first).
- Coordinates **4+ parties across 4 channels** in one gated workflow; deflects contact-center calls.
- KPIs surfaced on the demo dashboard: **days-to-settle**, **% touchless FNOL**, parties coordinated,
  CDS channels used.

## Repeatable offering (AWS Marketplace angle)

The engine is **domain-agnostic**: swap only the sub-agent roster, commit-gate rules, and document
templates to re-skin for **utilities** (outage coordination), **retail/logistics** (delivery + install),
**healthcare** (referral/PA scheduling), or **B2B finance** (dispute resolution). Ship the engine once;
sell a configured "Coordination Agent" per vertical.

## How the submission maps to the judging criteria

| Criterion | Weight | How we address it |
|---|---|---|
| **Technical Execution** | 40% | **Two AWS CDS services live at runtime** — Amazon SES and AWS End User Messaging (SMS), both provable via `scripts/send_live_cds.py` through the engine's own adapters (real AWS MessageIds); EUM RCS adapter validated against the botocore service model; WhatsApp via Meta Cloud API with **real Amazon Bedrock Nova Pro vision** triage; Bedrock AgentCore runtime deployed; DynamoDB persistence; SNS + Lambda + S3; least-privilege IAM; one-command CDK deploy; **56 automated tests, all passing**. |
| **Potential Value/Impact** | 20% | Attacks the 40.7-day claims cycle with a measurable days-to-settle KPI. |
| **Demo Presentation** | 20% | End-to-end agentic workflow (multimodal FNOL photo → vision triage → fan-out → tow/rental/repair → settlement) shown live, phone mirrored to the operator console in real time over SSE. |
| **Creativity** | 10% | Multi-party commit gate + a **code-enforced human-in-the-loop approval gate** before any payout + multimodal (vision) FNOL — beyond the single-agent reference pattern, and directly answering the 2026 "human stays in control" governance requirement. |
| **Functionality** | 10% | Runs end-to-end; graceful simulation fallback for reproducibility; scalable serverless design. |

## Try it

```bash
# Offline, no AWS needed — full FNOL -> settlement journey:
make demo            # SIMULATE_CHANNELS=true python scripts/measure_e2e.py
make test            # 56 unit/integration tests

# Prove TWO AWS CDS services live at runtime (real SES + real EUM SMS via the
# engine's own channel adapters; prints AWS MessageIds):
python3 scripts/send_live_cds.py

# Live UI (operator + customer phone), real Bedrock vision + SES + EUM SMS:
cp .env.example .env && $EDITOR .env    # set AWS_REGION, SES sender, EUM originator
./start.sh                              # dashboard on :8081 (proxies /api -> :8080)
./stop.sh

# Deploy to AWS:
cd infra && npm install && npx cdk deploy && cd ..
./scripts/sync_agent_src.sh && cd deployment/coeagent && agentcore deploy --yes
```

> **Before submitting, fill the three fields at the top of this file** (repo URL, deployed/interaction
> URL, ACE Opportunity ID with campaign code "AWS CDS Agentic AI Hackathon - Sept. 2026").

## What's next

- Add RCS **verified-sender step-up verification** on the adjuster's Approve card (the human-in-the-loop
  gate is already enforced in code; this hardens *who* can approve).
- Wire **AgentCore Payments** (GA 2026) so the settlement step disburses autonomously once the human
  approval is recorded within the gate.
- Publish a configured vertical as an AWS Marketplace listing.
