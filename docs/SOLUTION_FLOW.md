# Solution Flow — One Touch Resolve

The **end-to-end agentic workflow**, written for the demo and the judging rubric
("Does it include the end-to-end agentic workflow?" — Demo 20%).

Legend: **C**=Claimant · **R**=Repair shop · **P**=Parts supplier · **L**=Lienholder.
Channels: WhatsApp (EUM Social) · RCS/SMS (EUM) · Email (SES).

---

## 0. The thing that makes this agentic (not a script)

A supervisor agent on Bedrock AgentCore holds a **shared claim state** and drives **one sub-agent per
party**. The claim advances through a state machine, but a **commit gate** stands between
`PARTIES_ENGAGED` and `COMMITTED`: it will not let the claim progress until every *required* party is
`COMMITTED`, and when any party is `BLOCKED` it forces the supervisor to **re-plan**. That gate — not
the chat — is the agentic core.

```
NEW ─▶ FNOL_CAPTURED ─▶ PARTIES_ENGAGED ─▶[ COMMIT GATE ]─▶ COMMITTED ─▶ SETTLED
                                   ▲                │
                                   └──── re-plan ◀──┘   (any required party BLOCKED)
```

---

## 1. Happy-path + disruption journey (the demo)

| # | Actor / trigger | Channel | What the engine does | State / gate |
|---|---|---|---|---|
| 1 | **C** sends damage photo at FNOL | WhatsApp | Media → S3; Bedrock triages severity + est. repair days from the image | `NEW → FNOL_CAPTURED` |
| 2 | Supervisor opens claim | — | Writes claim record (DynamoDB) + session (AgentCore Memory, keyed by `actor_id`) | claim created |
| 3 | **Fan-out (parallel)**: estimate request to **R**; coverage notice to **L** | R: RCS→SMS · L: Email | Sub-agents engage each party; mark `NOTIFIED` | `FNOL_CAPTURED → PARTIES_ENGAGED` |
| 4 | **P** reports part back-ordered 5d | inbound | Parts sub-agent sets `P = BLOCKED` | **gate CLOSED** — names `parts_supplier` |
| 5 | **Re-plan** | WhatsApp (to C) | Supervisor offers rental, re-sources part (2d), proactively updates C | gate re-evaluated |
| 6 | **R** confirms appt; **L** acknowledges coverage | R, L | Sub-agents set `R, L = COMMITTED`; P now `COMMITTED` (2d) | all required committed |
| 7 | **R**'s RCS session degrades | RCS → **SMS fallback** | Same workflow continues on SMS; state untouched (channel continuity) | no re-auth |
| 8 | Gate opens | — | `commit_gate.try_commit()` advances the claim | `PARTIES_ENGAGED → COMMITTED` |
| 9 | Settlement issued | SES (L) + WhatsApp (C) | Settlement letter emailed; customer notified | `COMMITTED → SETTLED` |

Every row maps to a real tool in `agent/tools/claim_tools.py`
(`open_claim`, `engage_party`/`request_estimate`/`notify_lienholder`, `check_parts_eta`,
`send_message`, `commit_party`, `evaluate_commit_gate`, `continue_on_fallback`, `issue_settlement`).

---

## 2. Request lifecycle (one inbound message, end to end)

```
Inbound (WhatsApp / RCS / SMS)
   │
   ▼
AWS End User Messaging  /  EUM Social          ──▶  Amazon SNS (one topic per inbound channel)
                                                     │
                                                     ▼
                                          Dispatcher Lambda (channels/dispatcher.py)
                                           1. normalize SNS → event
                                           2. persist media → S3 (if any)
                                           3. de-dupe on inbound message id (DynamoDB, conditional write)
                                           4. invoke AgentCore runtime (by ARN)
                                                     │
                                                     ▼
                                   Bedrock AgentCore Runtime — Supervisor (Strands, Nova Pro)
                                     ├─ load cross-channel context (AgentCore Memory, actor_id)
                                     ├─ pick / drive the right sub-agent(s)
                                     ├─ call tools (Lambda) → mutate claim (DynamoDB)
                                     ├─ evaluate commit gate → advance or re-plan
                                     └─ emit outbound via channel router
                                                     │
                 ┌───────────────────────────────────┼───────────────────────────────┐
                 ▼                                    ▼                               ▼
         SendTextMessage                        WhatsApp send                     Amazon SES
         (RCS→SMS fallback, pool)               (EUM Social)                      (documents)
```

---

## 3. Decision logic at the gate (`agent/commit_gate.py`, pure/unit-tested)

```
required = parties where required_for_commit == True
if any(p.status == BLOCKED):      gate = CLOSED, reason names blocked parties  → supervisor RE-PLANS
elif any(p.status in {PENDING, NOTIFIED}):  gate = CLOSED, names pending parties → wait / nudge
else:                              gate = OPEN → advance NEW…→ COMMITTED
```

This is deliberately AWS-free so it is trivially testable and portable across verticals.

---

## 4. Re-skin points (same engine, new vertical)

Only three things change per vertical; the orchestration core, channel router, and cross-channel
memory stay constant:

| Swap | Insurance (this build) | Utilities | Healthcare (scheduling) | Logistics |
|---|---|---|---|---|
| **Sub-agent roster** | claimant · repair · parts · lienholder | customer · field crew · caregiver · backup facility | patient · clinic · payer · specialist | customer · courier · warehouse · installer |
| **Commit-gate rules** | all repair-chain parties commit before settle | crew + facility confirm before dispatch | all providers confirm before booking | all nodes confirm before delivery slot |
| **Document templates** | coverage / settlement letters | outage / restoration notices | appointment / instruction docs | delivery / POD notices |

Ship once → list a configured "Coordination Agent" per vertical on AWS Marketplace.
