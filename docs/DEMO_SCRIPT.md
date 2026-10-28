# 3-Minute Demo Video Script

**Goal:** show the *end-to-end agentic workflow* clearly (20% of score), with the two differentiators the
judges can see: the **multi-party commit gate** and **channel-aware continuity**.

**Setup for filming:** split screen. Left = the claim-state **dashboard** (`dashboard/index.html?data=state.json`).
Right = a terminal running `./scripts/simulate_demo.sh` (or four mock phone/email panes if using live channels).
Run `python scripts/export_dashboard.py` first so the dashboard reflects the real run.

---

### 0:00 – 0:20 — Hook (the problem)
> "Property insurance claims take **40.7 days** on average — the longest since 2008. The delay isn't the
> adjuster; it's that the customer, repair shop, parts supplier, and lienholder never talk to each other.
> Meet the **One Touch Resolve** — an agent on Amazon Bedrock AgentCore that coordinates all of
> them across AWS Communication Developer Services."

_On screen:_ title card → dashboard showing an empty claim.

### 0:20 – 0:50 — FNOL on WhatsApp
> "A policyholder reports a collision by sending a **photo over WhatsApp**. The supervisor agent triages
> severity and opens claim CLM-… — you can see the state move to **FNOL_CAPTURED**."

_On screen:_ WhatsApp photo message → dashboard state chip lights `FNOL_CAPTURED`; claimant party appears.

### 0:50 – 1:30 — Parallel fan-out (multi-agent)
> "The supervisor delegates to specialist sub-agents — one per party. It requests an estimate from the
> **repair shop over RCS**, and emails the **lienholder a coverage notice via Amazon SES** — in parallel.
> State moves to **PARTIES_ENGAGED**."

_On screen:_ two messages fire (RCS card + SES email); dashboard shows repair_shop = NOTIFIED, lienholder = NOTIFIED.

### 1:30 – 2:05 — Disruption → commit gate closes → re-plan
> "Now the twist. The part is **back-ordered five days**. Watch the **commit gate**: it stays **CLOSED**
> because a required party is blocked. A single-agent chatbot would stall here. Our supervisor **re-plans** —
> it arranges a **rental**, proactively tells the claimant on WhatsApp, and sources the part in two days."

_On screen:_ gate banner turns red "CLOSED — blocked: parts_supplier" → WhatsApp update to claimant →
parts flips to COMMITTED.

### 2:05 – 2:35 — Channel-aware continuity (RCS → SMS)
> "The repair shop's **RCS session degrades**. Because state lives in AgentCore Memory — not the channel —
> the **same workflow continues on SMS** with no lost context, no re-auth. That's channel-aware continuity,
> built on AWS End User Messaging's RCS-to-SMS fallback."

_On screen:_ repair_shop channel badge flips RCS → SMS; conversation continues seamlessly.

### 2:35 – 3:00 — Gate opens → settlement → close
> "All required parties have now committed — the **gate opens**, the claim advances to **COMMITTED**, and the
> engine issues the **settlement letter via SES** and notifies the claimant on WhatsApp. **SETTLED.**
> Four parties, four AWS CDS channels, one claim state — turning a 40-day process into days. And the same
> engine re-skins for utilities, retail, healthcare, and finance."

_On screen:_ gate turns green → state chips complete through `SETTLED`; KPI panel "40.7 → 15 days,
4 parties, 4 channels". End card with repo URL + "Built with AWS CDS + Amazon Bedrock AgentCore".

---

**Tips**
- Keep the terminal font large; pre-run once so timing is smooth.
- Narrate the *gate closing then opening* explicitly — it's the money shot.
- If demoing live channels, blur real phone numbers/emails.
