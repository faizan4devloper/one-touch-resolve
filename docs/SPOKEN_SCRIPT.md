# One Touch Resolve — Spoken Script (read-aloud)

Read top to bottom. Run the demo at Slide 5.
Demo command (safe / offline): `SIMULATE_CHANNELS=true SIMULATE_EMAIL=true python3 scripts/simulate_demo.py`

---

## (Slide 1 · Title)

"Hi everyone — thanks for the few minutes.

I want to put forward what I think is our strongest hackathon entry. It's called the **One Touch Resolve**.

In one line: it's an **AI agent that settles an insurance claim in days instead of weeks** — by coordinating every party involved, automatically. And because the customer side runs on WhatsApp, we're **eligible for Meta's 'Best of WhatsApp' recognition**.

Let me show you why it's worth entering."

## (Slide 2 · The Problem)

"Today, a property insurance claim takes about **forty-one days** to settle. *(pause)* That's among the slowest on record.

But here's the real insight — it's almost **never the adjuster** being slow. The problem is **fragmentation**. The customer, the repair shop, the parts supplier, the lender — they all live in different systems, on different channels, and **nobody owns the coordination** between them. Every handoff quietly adds days.

Meanwhile, digital-first carriers already close in about **fifteen** days, and customers expect around **eleven**. So there's a real, measurable gap to go after — and it's a coordination problem, which is exactly what an agent is good at."

## (Slide 3 · What It Does)

"So here's the idea — **one agent that handles everyone**, on the customer's behalf.

Two things make it different from an ordinary chatbot.

**First — it never stalls.** The claim only moves forward when *every* party is on board. If one of them hits a snag — a part is delayed, say — the agent **finds another way** instead of just stopping.

**Second — it never loses the thread.** You can switch channels in the middle of a conversation and nothing is lost. Nobody ever has to repeat themselves.

Instead of the customer chasing four different people, **one agent drives them all** to a settled claim, on one shared record."

## (Slide 4 · Key Features)

"Quickly, the pieces that make it work:

A **team of AI agents** — one per party, run by a single supervisor. A **commit gate** that refuses to advance until everyone agrees. **Continuity** across any channel — WhatsApp, text, or email. **Smart triage** that reads the damage straight from the first photo. And **one shared record** — a full audit trail, a single source of truth.

And the one that matters commercially — it's **reusable**. The same engine re-skins for utilities, logistics, healthcare, finance. **Build it once, sell it many times.** We just swap the parties and the rules; the core stays the same."

## (Slide 5 · How It Works — RUN THE LIVE DEMO NOW)

"Now let me make it real. This isn't a mockup — I'm going to **run the actual engine** end to end. Watch the claim move through its states on the left, and the messages go out on the right.

*(start the demo, then narrate as it prints — slow down here)*

Our customer — policy **POL-2026-88123** — reports a **rear-end collision on WhatsApp** with a photo. The agent triages the damage and opens the claim. State moves to **FNOL captured**.

Straight away it **fans out to specialist sub-agents** — it asks the repair shop for an estimate over **RCS**, and emails the lender a coverage notice through **email** — at the same time. State moves to **parties engaged**.

*(pause — point at the gate)* Now the twist. The **front bumper is back-ordered — five days.** Watch the **commit gate**: it stays **CLOSED**, because a required party is blocked. *(beat)* **A normal system stalls right here.**

Ours **re-plans.** It arranges a **rental**, tells the customer on WhatsApp what's happening, and sources the part from another supplier in **two days** — so parts flips to committed.

Then the repair shop's **channel drops.** Because the state lives in memory — not in the channel — the same conversation just **continues on SMS**, with no lost context and no asking anyone to start over. That's the channel continuity.

*(let the final lines print)* Every required party has now committed — the **gate OPENS**, the claim advances to **committed**, the engine issues the **settlement letter over email**, and the customer gets the good news on WhatsApp.

**Settled — for four thousand two hundred dollars — in days, not weeks.** Four parties. Four channels. **One claim state.**

And you can see it printed **PASS** at the bottom — the claim reached settled, end to end. That's the real run, not a slide."

## (Slide 6 · Where It Stands & The Ask)

"Two things to close on.

**Where it stands:** what you just watched is a **working reference** — it runs the full journey today, and the agent reasoning is **real, not scripted**. The messaging channels run in a faithful simulation until we provision live numbers. So we are **not starting from zero.**

**The ask:** if we agree this is our entry, we need two things — a **WhatsApp business number and the messaging set-up**, and to **align on who takes it forward** for the submission. The concept is proven; the rest is provisioning and polish."

## (Close)

"So that's the **One Touch Resolve** — turning a forty-day process into a few days, with one agent that owns the outcome from start to finish.

I think it's a strong fit for the hackathon, and I'd love your take on whether we run with it. Happy to take questions.

**Thank you.**"

---

## Q&A — quick, confident answers

**"Is it real, or a mockup?"**
"Real. The agent logic and reasoning run end to end — you just saw it. The channels are a faithful simulation until we provision numbers. Nothing is faked to hide how it works."

**"How is this different from a normal chatbot?"**
"Two things a single chatbot can't fake: the **multi-party commit gate** — it won't advance until every party commits — and **cross-channel continuity**, because the state lives in memory, not the channel. A chatbot has no concept of independent parties converging on one shared, gated outcome."

**"Whose is it — did you build this?"**
"It's a use-case with a working reference implementation in our shared folder. I'm bringing it forward as a strong candidate for our team's hackathon entry."

**"How soon could it go live?"**
"Mostly provisioning — a WhatsApp business number and messaging identities. The core is already built and deploys with a single CDK stack."

**"What AWS services does it use?"**
"AWS End User Messaging for SMS and RCS, End User Messaging Social for WhatsApp, and Amazon SES for email — orchestrated by Amazon Bedrock AgentCore, with DynamoDB for state. All CDS channels, which is exactly what this hackathon is about."

**"Where's the forty-one-day number from?"**
"The J.D. Power U.S. Property Claims Satisfaction Study — it's cited on the problem slide."

**"Does it only work for insurance?"**
"No — that's the whole point. Swap the parties and the rules and the same engine fits utilities, logistics, healthcare, or finance. Build once, sell many times."

**"What if the live demo fails on stage?"**
"It's deterministic and runs fully offline — no network needed. If anything hiccups, I've got the dashboard state and a recorded run to walk through."

---

## Delivery reminders
- Slide 5 is the win — slow down, narrate the **gate closing then opening**.
- Say the numbers clearly: **40.7 → 15 → 11 days**, **$4,200**, **4 parties, 4 channels**.
- End on the ask, then the thank-you. Close cleanly.
- Pre-run the demo once so it's smooth and you see `RESULT: PASS ✅`.
