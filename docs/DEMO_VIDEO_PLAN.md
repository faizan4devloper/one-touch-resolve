# Demo Video Plan — One Touch Resolve (≈3 min)

**Deadline:** Devpost submission closes **today 1:00 pm PDT**. Video must be **public on YouTube/Vimeo**,
~3 minutes, show the project **functioning**, no copyrighted music/trademarks, English.
**Judging:** Demo Presentation = 20% ("Does it include the end-to-end agentic workflow?").

> This plan uses the REAL demo surfaces that exist today. (The old `simulate_demo.sh` /
> `dashboard/` references in `DEMO_SCRIPT.md` are stale — ignore them.)

---

## 0. What we actually show (the real surfaces)

| Surface | Command / URL | Shows |
|---|---|---|
| **Operator dashboard + phone** | `./start.sh` → phone `:8080`, dashboard `:8081` | the split-screen hero: customer taps on the phone, Mission Control reacts live over SSE |
| **Timed end-to-end run** | `SIMULATE_CHANNELS=true python3 scripts/measure_e2e.py` | NEW→SETTLED across 5 parties / 4 channels, code-verified, in ms — the terminal proof |
| **Live CDS proof** | `python3 scripts/send_live_cds.py` | real Amazon SES + real EUM SMS MessageIds returned by AWS — "it's genuinely live" |
| **Architecture** | `docs/architecture.png` / the PPTX | the one overview visual the rules require |

**Recommended hero for the video:** the **phone + dashboard split screen** (`./start.sh`), because it's the
most visual and directly shows the end-to-end agentic workflow. Cut to the **terminal `measure_e2e`** run and
the **`send_live_cds` MessageIds** as proof beats.

---

## 1. Pre-flight (do once, before recording)

```bash
cd coordinated-outcome-engine
cp .env.example .env         # set AWS_REGION, SES sender, EUM originator if showing live CDS
make test                    # confirm 56 passing
SIMULATE_CHANNELS=true python3 scripts/measure_e2e.py   # confirm NEW->SETTLED PASS
./start.sh                   # phone :8080, dashboard :8081 — open both, do a full dry run
```

- Open **two browser windows side by side**: phone (`:8080`) left, dashboard (`:8081`) right.
- Do a **full practice run** of the phone journey so timing is smooth and the dashboard animates.
- If showing live CDS: pre-run `send_live_cds.py` once, confirm it prints MessageIds; **blur** real
  numbers/emails/account IDs in the recording.
- Have `docs/architecture.png` open in a tab for the overview beat.

**Recording setup**
- 1080p screen capture (OBS / QuickTime / Loom). 16:9.
- Large browser zoom so text is legible when compressed by YouTube.
- Mic test; quiet room. No background music unless you own the rights (safer: none).
- Plan for **2–3 takes**; it's only 3 minutes.

---

## 2. Shot list & narration (0:00 – 3:00)

> Narration is adapted from `DEMO_SCRIPT.md` — proven copy, retargeted to the real UI.
> Say the numbers clearly: **40.7 → 15 → 11 days**, **$4,200**, **5 parties, 4 channels**.

### 0:00–0:20 · Hook (problem)
**Screen:** title card → architecture.png briefly, or the empty dashboard ("Standing by").
> "Property insurance claims take **40.7 days** on average — the longest since 2008. The delay isn't the
> adjuster; it's that the customer, repair shop, parts supplier, and lienholder never talk to each other.
> **One Touch Resolve** is an agent on Amazon Bedrock AgentCore that coordinates all of them across
> AWS Communication Developer Services."

### 0:20–0:50 · FNOL on WhatsApp (multimodal)
**Screen:** phone app — customer sends the **damage photo**; dashboard flips to **FNOL_CAPTURED**, triage
severity/reasoning appears ("Nova Pro vision").
> "A policyholder reports a collision by sending a **photo on WhatsApp**. **Amazon Bedrock Nova Pro vision**
> reads the actual damage — severity, drivability — and opens the claim. State moves to **FNOL captured**."

### 0:50–1:30 · Parallel fan-out (multi-agent)
**Screen:** dashboard Agent-activity timeline streams; **fan-out event** shows recipients + channels; Parties
roster fills (repair_shop NOTIFIED on RCS, lienholder NOTIFIED on email). State → **PARTIES_ENGAGED**.
> "The supervisor delegates to **specialist sub-agents — one per party**. It requests an estimate from the
> **repair shop over RCS**, and emails the **lienholder a coverage notice via Amazon SES** — in parallel.
> You can see the single update **fan out to multiple parties, each on its own channel**."

### 1:30–2:05 · Disruption → commit gate CLOSED → re-plan (the money shot)
**Screen:** gate indicator turns **CLOSED — blocked: parts_supplier**; then the **rental** is reserved (real
fleet vehicle), claimant gets a proactive WhatsApp update, parts flips **COMMITTED**.
> "Now the twist — the part is **back-ordered five days**. Watch the **commit gate**: it stays **CLOSED**
> because a required party is blocked. A single-agent chatbot stalls here. Ours **re-plans** — it reserves a
> **real courtesy car** from the managed fleet, tells the claimant on WhatsApp, and sources the part in two
> days." *(Pause on the gate — this is the beat judges remember.)*

### 2:05–2:30 · Human-in-the-loop + continuity
**Screen:** gate **OPEN**; adjuster **Approve/Hold** card; channel badge flips **RCS → SMS**.
> "All parties committed — the gate **opens**. But **no money moves without a human**: the adjuster gets an
> **Approve/Hold** card, enforced in code. And when the repair shop's **RCS drops, the workflow continues on
> SMS** — state lives in AgentCore Memory, not the channel."

### 2:30–2:55 · Settlement + live proof
**Screen:** adjuster approves → **SETTLED**; settlement email (SES). Quick cut to terminal:
`send_live_cds.py` printing **real AWS MessageIds** (SES + EUM SMS).
> "On approval, the engine issues the **settlement letter via Amazon SES** and notifies the customer.
> **Settled — $4,200 — in days, not weeks.** And this is **really live**: here are real AWS MessageIds from
> Amazon SES and AWS End User Messaging."

### 2:55–3:00 · Close
**Screen:** architecture.png + end card (repo URL, "Built on AWS CDS + Amazon Bedrock AgentCore").
> "Five parties, four CDS channels, one claim state — and the same engine re-skins for utilities, retail,
> healthcare, and finance. **One Touch Resolve.**"

---

## 3. Editing checklist
- [ ] ≤ 3:00 total (judges may stop at 3:00 — front-load the agentic workflow).
- [ ] Shows the project **functioning** (live phone→dashboard), not just slides.
- [ ] The **gate CLOSED → re-plan → OPEN** sequence is clearly visible and narrated.
- [ ] Human-approval beat is shown (differentiator).
- [ ] One **live-proof** beat (MessageIds) for the "is it real?" question.
- [ ] Real phone numbers / emails / AWS account IDs **blurred**.
- [ ] No copyrighted music/trademarks.
- [ ] End card has the **repo URL**.
- [ ] Upload **public** to YouTube/Vimeo; paste link into the Devpost form.

## 4. Fallback if a live run misbehaves on camera
- Record the **`measure_e2e.py`** terminal run instead (deterministic, offline, always PASS) and narrate the
  same story over it — the dashboard screenshots can illustrate states.
- Keep `docs/architecture.png` on screen while narrating if the UI stalls.

## 5. Division of labor (to hit the deadline)
1. **Record** the phone+dashboard run (1 person, ~20 min incl. retakes).
2. **Record** the two terminal proof beats (`measure_e2e`, `send_live_cds`).
3. **Stitch + narrate** (voiceover over the screen capture) → export 1080p.
4. **Upload public** → paste link in Devpost → fill repo URL + deployed URL → submit.
