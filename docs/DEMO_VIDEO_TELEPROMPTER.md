# Teleprompter Script — One Touch Resolve (read straight through)

> Spoken words only. ~450 words ≈ 2:50 at a natural pace. Pause where you see  (…).
> Say numbers clearly. Don't rush the gate beat — that's the one that wins.

---

**[0:00 — HOOK]**

Property insurance claims take forty point seven days to settle on average — the longest since two‑thousand‑eight.  (…)  And the delay usually isn't the adjuster. It's that the customer, the repair shop, the parts supplier, and the lender never actually talk to each other. Nobody owns the coordination.

This is One Touch Resolve — an AI agent on Amazon Bedrock AgentCore that coordinates every party, across AWS Communication Developer Services, and drives the claim to settled.

**[0:20 — FNOL ON WHATSAPP]**

It starts when the policyholder reports a collision — by sending a photo on WhatsApp. Amazon Bedrock Nova Pro vision reads the actual damage from that photo — how severe it is, whether the car is drivable — and opens the claim. You can see the state move to F‑NOL captured.

**[0:50 — FAN-OUT]**

Now the supervisor delegates to specialist sub‑agents — one for each party. In parallel, it asks the repair shop for an estimate over R‑C‑S, and emails the lender a coverage notice through Amazon SES. Watch the timeline: one coordinated update, fanning out to multiple parties, each on the right channel. The claim moves to parties engaged.

**[1:30 — THE TWIST: GATE CLOSED → RE-PLAN]**

Then the twist. The part is back‑ordered — five days.  (…)  Watch the commit gate. It stays closed, because a required party is blocked.  (…)  A single‑agent chatbot would just stall right here.

Ours re‑plans. It reserves a real courtesy car from the managed fleet, tells the customer on WhatsApp what's happening, and sources the part from another supplier in two days. The parts supplier flips to committed.

**[2:05 — HUMAN APPROVAL + CONTINUITY]**

Now every required party has committed — so the gate opens. But no money moves without a human. The adjuster gets an Approve‑or‑Hold card — and that's enforced in code, not just a prompt.

And when the repair shop's R‑C‑S session drops, the same workflow just continues on S‑M‑S — no lost context, because the state lives in AgentCore Memory, not in the channel.

**[2:30 — SETTLEMENT + LIVE PROOF]**

The adjuster approves. The engine issues the settlement letter through Amazon SES and notifies the customer.  (…)  Settled — four thousand two hundred dollars — in days, not weeks.

And this is genuinely live. These are real message I‑Ds, returned by Amazon SES and AWS End User Messaging.

**[2:55 — CLOSE]**

Five parties. Four CDS channels. One claim state. And the same engine re‑skins for utilities, retail, healthcare, and finance. Build it once — sell it everywhere.

This is One Touch Resolve.

---

**Word count ≈ 450.  Target ≈ 2:50.  Hard stop 3:00.**

**Pace reminders:** slow down on the gate (1:30–2:05). Hit the numbers: forty‑point‑seven → fifteen → eleven days; four‑thousand‑two‑hundred dollars; five parties, four channels. Close clean — don't trail off.
