# One Touch Resolve — Research & Positioning (2026-10-17)

Competitive and problem research for the **AWS CDS Agentic AI Partner Hackathon**.
Everything here is sourced from public 2026 material (links inline).

---

## 1. Hackathon facts

- **Deadline:** Oct 28, 2026 @ 1:00pm PDT. **926** participants.
- **Prizes:** $18k / $8k / $4k + **$10k Meta "Best of WhatsApp."**
- **Build with:** at least one AWS CDS service — EUM (RCS/SMS), EUM Social (WhatsApp), SES.
  Amazon Bedrock AgentCore recommended, not required.
- **Judging weights:** Technical Execution **40%** (well-architected, **reproducible**,
  multiple CDS services), Potential Value/Impact **20%**, Demo Presentation **20%**
  (end-to-end agentic workflow), Creativity **10%**, Functionality **10%**.
- **Required submission items:** GitHub repo (OSS license if public; must show CDS at
  runtime) · architecture diagram · text description · ~3-min video · deployed URL or
  interaction instructions · ACE opportunity ID with campaign code
  "AWS CDS Agentic AI Hackathon -Sept. 2026". Meta prize needs a written description of
  how EUM Social (WhatsApp) was used.

## 2. Problem data (validated, current)

| Metric | Figure | Source |
|---|---|---|
| FNOL → final payment cycle time | **40.7 days** (down 3.4 YoY) | J.D. Power 2026 U.S. Property Claims Satisfaction Study |
| Repair cycle time | **29.6 days** | J.D. Power 2026 |
| Historical context | both **among longest since tracking began in 2008** | Insurance Business Mag / Decerto 2026 |
| Adjuster load | **150–200 simultaneous claims**, coordinating repair shops, medical providers, multiple stakeholders | Sonant.ai 2026 |
| Third-party spend (claims-heavy portfolios) | **up to 80% of operating expense** | Inverto 2026 |

## 3. Analyst validation of the thesis — the headline asset

**L.E.K. Consulting, "From Fragmentation to Orchestration" (Aug 11, 2026):**

- "Value is moving decisively from performing individual claims tasks to **orchestrating
  the ecosystem that connects them**."
- "The key strategic question is no longer who performs individual claims tasks most
  effectively but **who controls the workflow, data and decision-making layer that
  coordinates the ecosystem**."
- "The challenge is no longer access to capability. It is **coordination**." — Sam Halliday
- "The future of claims will not be defined by who performs individual tasks. It will be
  defined by **who orchestrates the ecosystem**." — David Hitsky
- Vendor archetypes: point solution / network / **platform** — distinguished by how much
  of the ecosystem they coordinate. The **orchestration layer is the durable, defensible
  position**.

> Use this to reframe the project from "a chatbot" to "the orchestration control point
> the industry's own analysts say is the position worth owning."

## 4. Competitive landscape — all single-party customer agents

Plivo, Infobip AgentOS, Lorikeet, Boost.ai (Acorn: 96% containment / 60k monthly chats),
Clerk.AI, getvocal, Cresta — **all** do single-agent-to-**one party** (the customer),
omnichannel, context preserved. **None coordinate multiple independent external parties
to a gated outcome.**

Lorikeet even defines a *complex* claim as requiring "multi-party coordination… status
orchestration over days/weeks" — yet their product still only handles the customer
conversation. **That is the whitespace.**

## 5. GitHub prior-art check

- **Closest repo:** `elizabethfuentes12/whatsapp-ai-agent-sample-for-aws-agentcore`
  (13★, AWS DevRel, MIT). Overlaps: AgentCore Runtime + Memory, Strands, EUM Social
  WhatsApp via SNS→Lambda, and **cross-channel memory keyed by `actor_id`**.
  → **Channel-continuity via `actor_id` is NOT novel** — it is the canonical AWS pattern.
- AWS samples (`awslabs/agentcore-samples`, `sample-bedrock-agentcore-twilio`,
  `hermesagent`) are all single-agent multi-channel. **None do multi-party coordination
  or a commit gate.**

## 6. Our moat (what to lead with)

1. **Multi-party = multi-agent** — one sub-agent per **external party** (claimant, repair
   shop, parts supplier, lienholder), not per channel. Unique.
2. **The multi-party commit gate** — a gated claim state machine that blocks advancement
   until every required party `COMMITTED`, and re-plans on `BLOCKED`. Unique vs. both
   competitors and existing repos. **This is the hero.**
3. **Insurance FNOL → settlement** domain with a real, measurable outcome.

## 7. Strategic direction

- **Lead with the commit gate** — the only genuinely novel element. Make it the hero of
  the 3-min demo.
- **Demote channel-continuity** to "table stakes we also do well" (AWS's own sample
  already demonstrates it; don't claim it as the innovation).
- **Open the pitch**: 40.7-day stat + L.E.K. orchestration quote → fragmentation problem
  → commit gate as the orchestration mechanism → cross-industry re-skin (Marketplace).
- **Reproducibility = 40% of score.** The "remove all mocks" change hurt this. Restore an
  offline/simulated demo **or** ship a fully deployed live URL so judges can run it.
  Pre-removal backup: `coordinated-outcome-engine-backup-20261017_145133.tgz`.

---

## 8. Real people's problems → features (voice-of-customer)

Sourced from customer forums, BBB complaints, and body-shop/adjuster articles (2026).
Use these as direct quotes in the pitch — judges respond to the victim, not the analyst.

### A. Policyholder pain (the customer)
| Real complaint (sourced) | Feature that covers it |
|---|---|
| "Since May 18 2026, I have not received any meaningful updates or communication." (BBB, First Chicago) — silence/ghosting | Proactive push on the customer's channel at every state change (WhatsApp/RCS); customer never chases. |
| "Why can't I get a hold of my adjuster? They won't answer." (Quora) — unreachable, phone tag | Zero-call, tap-only async journey (ZCAA); agent reaches out first. |
| "4 months, no repairs due to delays… directed me to a body shop of their choice." (BBB, UAIC) — stalls, no transparency | Shared claim state + live status visible across all parties. |
| "Running out of rental car coverage while your car sits in limbo." (Lee.net) — downstream harm | Re-plan on BLOCKED auto-offers a rental and keeps timeline moving. |

### B. The hidden pain — the OTHER parties (our whitespace)
| Real complaint (sourced) | Feature that covers it |
|---|---|
| "Coordination tasks between the insurer and repair providers" keep claims open (River Cities) | Multi-party = multi-agent; a sub-agent drives each party in parallel. |
| "Missing paperwork… the request gets lost in the shuffle." (EverybodyLovesYourMoney) | Commit gate names exactly who/what is outstanding; nothing gets lost. |
| "Ask who has the file today, whether liability is accepted, whether inspection is done… short lists are harder to dodge." (GoCarLife) — customer told to manually chase a checklist | The commit gate IS that checklist, automated; the engine chases parties. |
| "Delayed payment processing… impacting the shop's cash flow." (Proline) — repair-shop pain | Gated settlement + SES payment notice fire automatically once all commit. |
| "When body shop and insurer disagree… frustrating delays." (Lee.net/AppraisalEngine) — disputes with no owner | Supervisor reconciles conflicting/late replies at the gate; the engine OWNS coordination. |

### Core insight
Every source says the same thing: "nobody owns the coordination, so the customer is left
chasing a checklist across parties who don't talk to each other." The commit gate is
literally "the checklist, automated, with an owner."

### Honest gap (roadmap, do NOT overclaim)
Complaints also cite liability disputes and statutory acknowledgment deadlines (15–40
business days by state). The engine coordinates operational parties well but does NOT
adjudicate liability or track statutory deadlines today. Credible roadmap item:
a compliance-timer / liability sub-agent.

