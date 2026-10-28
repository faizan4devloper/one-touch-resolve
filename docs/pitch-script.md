# Pitch Script — One Touch Resolve (v2, research-backed)

**Length:** ~3 minutes spoken (hackathon video target) · **Deck:** `pitch-deck.html`
Written to be spoken — confident, concrete, no jargon. Judging weights it maps to are noted in
brackets for our own reference (not spoken): [Impact 20%] [Creativity 10%] [Tech 40%]
[Functionality 10%] [Demo 20%].

---

### Slide 1 · Title — the one-liner  [Impact]

"This is the **One Touch Resolve**.

One sentence: it's an agentic system that settles an insurance claim in **days instead of weeks** —
not by answering the customer faster, but by **coordinating every party** the claim depends on, and
refusing to move forward until they all commit.

The customer side runs on **WhatsApp**, so it's also in the running for Meta's Best-of-WhatsApp prize."

*→ advance*

---

### Slide 2 · The Problem — open with the victim  [Impact 20%]

"Here's a real complaint, filed this year:

> *'Four months. No repairs. Due to delays in the process.'*

That's not rare. Property claims now take **40.7 days** on average from first notice to final payment —
among the slowest on record (J.D. Power, 2026).

And here's the key insight: **it is almost never the adjuster being slow.** The delay lives in the
**gaps between parties** — the customer, the repair shop, the parts supplier, the lender each sit in a
different system on a different channel, and **nobody owns the coordination** between them.

Customers are literally advised to *manually chase a checklist* — 'ask who has the file today, ask if
the inspection's done.' That checklist is the product opportunity."

*→ advance*

---

### Slide 3 · Why now — the whole industry agrees  [Impact + Creativity]

"This isn't just our opinion. L.E.K. Consulting, this year, put it bluntly:

> *'The future of claims will not be defined by who performs individual tasks. It will be defined by
> who **orchestrates the ecosystem**.'*

Every tool on the market today builds a smarter agent for **one party — the customer.**
**Nobody automates the coordination *between* parties.** That's the whitespace we take."

*→ advance*

---

### Slide 4 · What it does — lead with the gate  [Creativity 10%]

"The core idea is a **multi-party commit gate.**

The supervisor spins up one specialist agent per party — claimant, repair shop, parts, lender — and
**blocks the claim from advancing until every required party has committed.** If one gets stuck — a
part's back-ordered — it doesn't stall. It **re-plans**: arranges a rental, sources the part elsewhere,
keeps the customer informed, and re-checks the gate.

A single-agent chatbot *structurally cannot* do this — there's no notion of independent parties
converging on one shared, gated state. That's our moat.

Channel continuity — picking up on SMS when RCS drops — we also do, cleanly. But the gate is the
innovation."

*→ advance*

---

### Slide 5 · How it works — the animated flow  [Demo 20%] [Functionality 10%]

"Let me make it real. Watch the steps.

*(pause — let the animation play)*

Customer reports a rear-end collision on **WhatsApp** with a photo. Bedrock triages the damage straight
from the image — severity, repair days — and opens the claim. The supervisor fans out **in parallel**:
the repair shop on **RCS**, the lender on **email**.

Then the twist — **bumper back-ordered, five days.** The commit gate **closes** and names exactly who's
blocking. A normal system stalls here. Ours re-plans: rental arranged, part re-sourced in two days,
customer updated. The repair shop's RCS drops — it continues on **SMS**, same state, no repeating.

Every party commits, the gate **opens**, and the claim **settles — in days, not weeks.**"

*→ advance*

---

### Slide 6 · Tech + the ask  [Tech 40%]

"Under the hood: **Amazon Bedrock AgentCore** runs the supervisor and sub-agents with shared Memory;
**all three AWS CDS channels** — End User Messaging RCS/SMS, EUM Social WhatsApp, and SES — are the
communications backbone; Lambda, DynamoDB, SNS and S3 hold it together, deployed by one CDK stack.

Where it stands: the orchestration core, commit gate, and channel layer are built and tested, and the
AI triage is a real Bedrock call. It's also **re-skinnable** — swap the party roster and rules and the
same engine fits utilities, logistics, healthcare, finance. Build once, list on AWS Marketplace, sell
per vertical.

The ask: provision the WhatsApp number and messaging identities, and record the demo. The concept is
proven; the rest is provisioning and polish.

**Thank you.**"

---

## If they ask…

- **"How is this different from Infobip / Lorikeet / a WhatsApp bot?"**
  "Those are excellent — at talking to *one* party, the customer. We coordinate *all* the parties and
  gate the outcome on their commitments. L.E.K. calls that orchestration layer the position worth
  owning. It's a different category, not a better chatbot."

- **"Is the channel-continuity the novel part?"**
  "No — and we're honest about that. Cross-channel memory via a shared actor id is a known AWS pattern;
  there's even a public sample. Our novel contribution is the **multi-party commit gate** and the
  re-plan loop. That's what we lead with."

- **"Is it real or a mockup?"**
  "The commit gate, state machine, channel adapters and CDK infra are real and unit-tested; the AI
  triage is a real Bedrock Converse call. For the judge-runnable demo we provide a faithful simulation
  of the carriers so it reproduces with zero channel setup, plus a live path once numbers are
  provisioned. Nothing is faked to hide how it works."

- **"Where's the 40.7-day number from?"** "J.D. Power 2026 U.S. Property Claims Satisfaction Study."

- **"What *doesn't* it do yet?"**
  "It coordinates operational parties. It does **not** adjudicate liability or track statutory
  acknowledgment deadlines yet — that's a clear roadmap item: a compliance-timer sub-agent."

- **"Does it only work for insurance?"**
  "No. Swap parties + gate rules + templates and the same engine fits utilities, logistics, healthcare,
  finance. That's the repeatable-offering story."

## Delivery reminders
- Open on the real complaint quote — let it land before the stat.
- Slide 4 (the gate) and Slide 5 (the animation) are the moments that win. Slow down there.
- Lead with the gate, demote channel-continuity to "we also do this cleanly."
- Keep under 3 minutes for the submission video; close on the ask, then thank-you.

---

## Competitive sharpening (the one contrast to hammer)

Every other entry in this space — including strong omnichannel-agent builds —
coordinates **one agent to one person at a time**: page an engineer, message a
sponsor, answer a staff question. That is **notifications and replies to
individuals**.

The One Touch Resolve coordinates a **multi-party outcome**: it blocks a
shared state until *N independent parties converge*, and re-plans when any one is
blocked. 

> **The line to say:** "Others send the right message to the right person on the
> right channel. We get **four parties who don't know each other to converge on
> one settled outcome** — and we refuse to advance until they do. That gate is a
> thing a one-to-one assistant structurally cannot have."

Say it once, plainly, on Slide 4. It is the single clearest reason to pick us.

## Credibility proof points (keep in your back pocket for judges)

These exist to answer "is this real?" with evidence, not adjectives:

- **Correctness is enforced in code, not the prompt.** State-advancing tools
  read the record back before reporting success — *a failed write is never
  reported as done* (`agent/safety.py`, see `docs/AGENT_SAFETY.md`). Identity is
  pinned from the verified inbound event, so the model can't be talked into
  acting on someone else's record.
- **The gate is a pure, tested state machine** — not model judgment.
- **CDS payloads are validated against the AWS API contract** in CI
  (`tests/test_cds_payloads.py`), so our SMS/RCS/WhatsApp/SES sends match the
  real service model.
- **One measured run:** we can show a claim going **NEW → SETTLED across 4
  parties and 4 channels end-to-end in a few milliseconds** on the local harness
  (`scripts/measure_e2e.py`) — a real, reproducible number (it even exercises the
  parts-back-ordered re-plan and the RCS→SMS continuity), not a projection.
- **38 passing tests** across the gate, tools, dedupe, dispatcher, channels and
  the ZCAA journey; the whole thing runs offline via `SIMULATE_CHANNELS`.

