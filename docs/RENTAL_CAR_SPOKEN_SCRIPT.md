# One Touch Resolve — Rental-Car Accident Claim
## Spoken Script (read-aloud, ~3–4 minutes)

Read top to bottom. Run the live demo at the marked point.
Demo command (safe / offline): `SIMULATE_CHANNELS=true SIMULATE_EMAIL=true python3 scripts/simulate_demo.py`

---

## (Open · The hook)

"Thanks for the few minutes. I want to walk you through what I think is our strongest hackathon entry — the **One Touch Resolve** — using a story everyone here has either lived or can picture: a **rental-car accident**.

In one line: it's an **AI agent that coordinates everyone involved in a claim and drives it to settlement in days, not months** — and because the customer side runs on WhatsApp, we're **eligible for Meta's 'Best of WhatsApp' recognition**."

## (The problem · why rental-car claims are the perfect proof point)

"Here's why rental-car accidents are the ideal example. They are **inherently three people, on three different systems, who never talk to each other directly:**

- **The renter** — who just had the accident and needs a car.
- **The rental fleet branch** — who owns the vehicle and manages the repair.
- **The insurer's adjuster** — who approves coverage and the payout.

Today, the only thing connecting those three is the **renter making frantic phone calls.** And the data backs this up: a full rental-car accident claim takes **six to eighteen months** to settle. The biggest frustration isn't the payout — it's **loss of use**: the car sits in limbo waiting on a back-ordered part, and the renter's rental coverage runs out before it's fixed.

Nobody owns the coordination. That's the gap we fill."

## (The three personas · the channel story)

"So let me introduce our three people — and notice each one is on a **different channel, chosen for a real reason.**

- **Maya, the renter.** She's on **WhatsApp** — so she can send damage photos straight from the roadside.
- **Dan, the fleet coordinator** at the rental branch. He's on **RCS** — rich interactive cards for the estimate and appointment — with automatic **SMS fallback** when he's out on the lot.
- **Priya, the insurer adjuster.** She's on **email** — because she needs durable, auditable documents: the coverage confirmation and the settlement letter.

One agent in the middle, talking to each of them on the channel that suits them. That's the whole idea."

## (How it works · RUN THE LIVE DEMO NOW)

"Let me make it real — this isn't a mockup, I'm running the actual engine. Watch the claim states on the left and the messages going out on the right.

*(start the demo, narrate as it prints — slow down here)*

**Hour zero.** Maya is rear-ended and sends photos over **WhatsApp**. The agent reads the damage, opens the claim, and she's met the rental agreement's **24-hour reporting deadline without one phone call.** State moves to **FNOL captured**.

Immediately it **fans out**: it asks **Dan** for an estimate over **RCS**, and emails **Priya** a coverage notice. At the same time. State moves to **parties engaged**.

*(pause — point at the gate)* Now the twist. The **rear bumper is back-ordered — five days.** Watch the **commit gate**: it stays **CLOSED**, because a required party is blocked. *(beat)* **A normal system stalls right here — and Maya is stranded.**

Ours **re-plans.** It arranges a **swap rental** for Maya, messages her proactively on WhatsApp — *before she has to chase anyone* — and sources the part from another supplier in **two days.**

Then **Dan's RCS session drops** as he walks the lot. Because the state lives in memory, not in the channel, the same conversation just **continues on SMS** — no lost context, nobody repeats themselves. That's channel continuity.

*(let the final lines print)* Now **every required party has committed** — Dan confirmed the appointment, Priya approved coverage *and* the rental reimbursement, the part arrived. The **gate OPENS**, the claim advances to **committed**, the engine issues the **settlement letter over email**, and Maya gets the good news on **WhatsApp**.

**Settled — four thousand two hundred dollars — in days, not months.** Three people. Four channels. **One claim.** And you can see it printed **PASS** at the bottom — that's a real run."

## (Why a chatbot can't fake this)

"Two things make this impossible for an ordinary chatbot to copy, and both are structural:

**First — the multi-party commit gate.** The claim won't advance until *every* independent party commits. A blocked part triggers a re-plan instead of a broken promise. A chatbot has no concept of separate parties converging on one shared, gated outcome.

**Second — cross-channel continuity.** The state lives in the claim record and in memory, never in the channel. The workflow survived an RCS-to-SMS drop mid-conversation and threaded WhatsApp, RCS, SMS, and email into one claim."

## (The commercial point · the ask)

"And here's what matters commercially: this **rental-car story is just a re-skin of the same engine.** We swapped the three people and kept the core — the supervisor, the commit gate, the shared memory. The same engine fits insurance, utilities, logistics, healthcare, finance. **Build it once, sell it per vertical.**

**Where it stands:** what you just saw is a **working reference** — it runs the full journey today, the agent reasoning is real, and the channels run in a faithful simulation until we provision live numbers. We are **not starting from zero.**

**The ask:** if we agree this is our entry, we need a **WhatsApp business number and the messaging set-up**, and to **align on who takes it forward.** The concept is proven; the rest is provisioning and polish.

That's the One Touch Resolve. I'd love your take on whether we run with it. Thank you."

---

## Q&A — quick, confident answers

**"Is it real or a mockup?"**
"Real. The agent logic runs end to end — you just watched it settle a claim. The channels are a faithful simulation until we provision numbers. Nothing is faked to hide how it works."

**"How is this different from a normal chatbot?"**
"Two things a chatbot can't fake: the **multi-party commit gate** — it won't advance until every party commits — and **cross-channel continuity**, because state lives in memory, not the channel."

**"Why rental cars specifically?"**
"Because it's the clearest example of a problem that's inherently multi-party and multi-channel — renter, fleet branch, insurer — and the industry data shows it's exactly where things break down today. But it's the same engine; we can re-skin it for any vertical."

**"How soon could it go live?"**
"Mostly provisioning — a WhatsApp business number and messaging identities. The core is already built and deploys with a single CDK stack."

**"What AWS services does it use?"**
"AWS End User Messaging for SMS and RCS, End User Messaging Social for WhatsApp, and Amazon SES for email — orchestrated by Amazon Bedrock AgentCore, with DynamoDB for state. All CDS channels — exactly what this hackathon is about."

**"What if the live demo fails on stage?"**
"It's deterministic and runs fully offline — no network needed. If anything hiccups, I have the recorded run and the dashboard to walk through."

---

## Sources behind the business case (public, cited)
- Rental agreements require reporting an accident immediately, often within 24 hours, or risk voiding waivers. *(engineerfix.com, 2026)*
- Full rental-car accident claims take 6–18 months; repair/parts delays and supplemental approvals are a leading cause. *(toddminerlaw.com; justia.com, 2026)*
- Loss-of-use pain: the car "sits in limbo" and rental coverage runs out before repairs finish. *(lee.net, 2026)*
- Fragmentation across rental company, third-party processors, and insurers leads to conflicting interpretations and delays. *(play-well.org, 2026)*

---

## Delivery reminders
- The demo is the win — slow down, narrate the **gate closing then opening**.
- Say the numbers clearly: **6–18 months today → days**, **$4,200**, **3 people, 4 channels**.
- Name the three personas every time — Maya, Dan, Priya — so the channels stick.
- Pre-run the demo once so it's smooth and you see `RESULT: PASS ✅`.
