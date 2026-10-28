# Architecture — One Touch Resolve (Insurance Claims Coordination Agent)

## 1. Overview

The One Touch Resolve is an **agentic omnichannel orchestrator**. A supervisor agent on
**Amazon Bedrock AgentCore** coordinates multiple independent external parties — each on the AWS CDS
channel chosen for a real reason — to drive an insurance claim from **First Notice of Loss (FNOL)** to
**settlement**, with a single shared claim state that follows each participant across channels.

**Why this matters (2026):** property claims take **40.7 days** FNOL→final payment (J.D. Power 2026) —
and the delay lives in the *gaps between parties*, not with any one person. L.E.K. Consulting (2026):
*"The future of claims will … be defined by who **orchestrates the ecosystem**."* Every tool on the
market automates the **customer** conversation; this engine automates the **coordination between
parties**. See `docs/RESEARCH_AND_POSITIONING.md` for the full problem/competitive analysis.

## 2. Design principles

1. **Multi-party = multi-agent (the moat).** Each external party is owned by a specialist sub-agent
   under a supervisor (AgentCore multi-agent collaboration, GA March 2025). A single-agent chatbot
   cannot reproduce independent parties converging on one shared, gated state.
2. **Commit gate before action (the hero mechanic).** The claim never advances to a committing step
   until *all required parties have committed*. Late/conflicting replies are reconciled; any party
   failure triggers a **re-plan** (e.g. back-ordered part → offer rental, re-source, re-evaluate).
3. **One case state, many channels.** AgentCore Memory (keyed by `actor_id`) + a DynamoDB claim record
   are the single source of truth. Channels are interchangeable transports over the same state.
   *(Note: cross-channel memory via a shared `actor_id` is a known AWS pattern — we do it cleanly, but
   it is table stakes, not our novelty. The novelty is the multi-party commit gate above.)*
4. **Right channel for the job.**
   - **WhatsApp (EUM Social)** — rich two-way media at FNOL (damage photos/video/voice).
   - **RCS (EUM)** — verified-sender interactive cards / choices (appointment cards, estimate requests).
   - **SMS (EUM)** — time-critical reach + automatic fallback when RCS is unavailable.
   - **SES** — durable, auditable documents (coverage confirmation, settlement letter, lienholder notice).

## 3. Component diagram

```
                          ┌───────────────────────────────────────────────┐
   Policyholder  ── WhatsApp ─┐                                            │
   Repair shop   ── RCS/SMS ──┤ AWS End User Messaging (SMS/RCS)           │
   Lienholder    ── email ────┤ AWS End User Messaging Social (WhatsApp)   │
                              │ Amazon SES                                 │
                          └────────────────────┬──────────────────────────┘
                                               │ inbound events publish to
                                               ▼
                                     ┌──────────────────┐
                                     │  Amazon SNS       │  (one topic per inbound channel)
                                     └─────────┬─────────┘
                                               │ triggers
                                               ▼
                                     ┌──────────────────┐
                                     │ Dispatcher Lambda │  channels/dispatcher.py
                                     │  - normalize event│
                                     │  - resolve actor  │
                                     │  - invoke agent   │
                                     └─────────┬─────────┘
                                               │ invoke_agent_runtime
                                               ▼
                    ┌────────────────────────────────────────────────────────┐
                    │        Amazon Bedrock AgentCore Runtime                  │
                    │  Supervisor agent (Strands SDK, Amazon Nova Pro)        │
                    │   ├─ AgentCore Memory  (claim state per actor_id)        │
                    │   ├─ Sub-agents: Claimant · RepairShop · Parts · Lien    │
                    │   └─ Commit gate (agent/commit_gate.py)                  │
                    └───────────────┬────────────────────────────────────────┘
                                    │ tool calls (Lambda)
        ┌───────────────────────────┼───────────────────────────────────────────┐
        ▼                           ▼                        ▼                    ▼
  open_claim /             request_estimate /          notify_lienholder /   send_message
  update_claim             check_parts_eta             coverage_letter       (channel router)
        │                           │                        │                    │
        └──────────────┬────────────┴───────────┬────────────┘                    │
                       ▼                         ▼                                 ▼
              ┌──────────────────┐      ┌──────────────────┐            ┌────────────────────┐
              │  Amazon DynamoDB │      │  Amazon DynamoDB │            │  AWS CDS outbound  │
              │  coe-claims      │      │  coe-parties     │            │  RCS→SMS · WA · SES│
              └──────────────────┘      └──────────────────┘            └────────────────────┘
```

## 4. Data flow — the demo journey

| # | Step | Channel | State transition |
|---|------|---------|------------------|
| 1 | Policyholder sends damage photo/video | WhatsApp (EUM Social) | `NEW → FNOL_CAPTURED` |
| 2 | Supervisor opens claim, triages severity | — | claim record created in DynamoDB + AgentCore Memory |
| 3 | Fan-out: estimate request to repair shop | RCS→SMS (EUM) | `FNOL_CAPTURED → PARTIES_ENGAGED` |
| 4 | Fan-out: coverage note to lienholder | SES | party record: lienholder = `notified` |
| 5 | Repair shop replies: part back-ordered 5 days | inbound SMS | commit gate: repair = `blocked` |
| 6 | Re-plan: propose rental, update timeline | WhatsApp | proactive claimant update |
| 7 | RCS session degrades → continue on SMS | RCS→**SMS fallback** | same state, no re-auth (channel continuity) |
| 8 | All parties commit → settlement letter | SES | `PARTIES_ENGAGED → COMMITTED → SETTLED` |

## 5. Cross-channel continuity (the RCS→SMS mechanic)

AWS End User Messaging uses the **same `SendTextMessage` API** for RCS and SMS. When the origination
identity is a **phone pool** that contains both an **AWS RCS Agent** and a **dedicated SMS number/sender
ID**, the service attempts RCS first and **automatically falls back to SMS** if the device/carrier does
not support RCS.

> **Constraint (verified, AWS EUM docs 2026):** shared SMS routes are **not** supported as RCS fallback.
> The pool/account must contain a **dedicated originator** valid for the destination country, or the
> message fails.

The engine treats the channel as a property of the *message*, not the *conversation*. Because state lives
in AgentCore Memory + DynamoDB (never in the transport), a workflow that starts on RCS continues on SMS
with full context. `channels/eum_messaging.py` sends via the pool; `agent/commit_gate.py` and the claim
record are channel-agnostic.

## 6. AWS services used

**AWS Communication Developer Services (required):**
- AWS End User Messaging — **SMS** and **RCS** (two-way, pool-based, RCS→SMS fallback)
- AWS End User Messaging **Social — WhatsApp**
- Amazon **SES**

**Agentic + supporting AWS services:**
- Amazon **Bedrock AgentCore** — Runtime, Memory, multi-agent collaboration (Strands SDK, Nova Pro)
- **AWS Lambda** — dispatcher + tools
- Amazon **SNS** — inbound event fan-in
- Amazon **DynamoDB** — cross-channel claim & party state
- Amazon **S3** — inbound media (WhatsApp/RCS attachments)
- **AWS IAM** — least-privilege roles
- Amazon **CloudWatch** — metrics/alarms on inbound processing

## 7. Scalability & reliability

- **Stateless Lambdas** behind SNS scale horizontally; state is externalized to DynamoDB + AgentCore Memory.
- **DLQ** on SNS subscriptions captures unprocessed inbound messages for retry (AWS best practice).
- **Pool-based sending** provides origination-identity failover in addition to RCS→SMS fallback.
- **Idempotency**: inbound messages carry `inboundMessageId`; the dispatcher de-dupes on it.

## 8. Security

- No secrets in code; all identifiers come from environment / SSM parameters.
- Least-privilege IAM per Lambda (send-message, dynamodb, ses, bedrock-agentcore only).
- Step-up verification (RCS verified sender) recommended before any money-moving step.
- PII (claimant phone/email) is referenced by key, not logged in plaintext.

## 9. Sources for the business case

- J.D. Power **2026** U.S. Property Claims Satisfaction Study — 40.7-day FNOL→final payment; 29.6-day
  repair cycle; both among the longest since tracking began in 2008 (Insurance Business Mag / Decerto 2026).
- **L.E.K. Consulting, "From Fragmentation to Orchestration" (Aug 2026)** — value is moving from
  performing claims tasks to *orchestrating the ecosystem*; the orchestration layer is the defensible
  position. Validates the multi-party thesis.
- Sonant.ai (2026) — adjusters handle **150–200 simultaneous claims** coordinating repair shops, medical
  providers and multiple stakeholders. Inverto (2026) — third-party spend up to **80%** of claims-heavy
  operating expense.
- Voice-of-customer (BBB complaints 2026; GoCarLife/EverybodyLovesYourMoney 2026) — "4 months, no
  repairs due to delays"; customers advised to *manually chase a checklist* of which party holds the file.
- AWS EUM RCS→SMS fallback constraints — AWS End User Messaging SMS User Guide (2026).
- AgentCore multi-agent collaboration GA — AWS, March 2025; AgentCore Runtime GA — AWS, 2026.

> Full analysis, competitive landscape, and GitHub prior-art check: `docs/RESEARCH_AND_POSITIONING.md`.
> End-to-end agentic workflow: `docs/SOLUTION_FLOW.md`.
