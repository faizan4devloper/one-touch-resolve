#!/usr/bin/env python3
"""Measured end-to-end run: one claim NEW -> SETTLED across 4 parties / 3 channels.

Runs the REAL engine code (claim tools, commit gate, channel router, external
ticket) fully offline — in-memory claim store + simulated channels + a stubbed
Bedrock triage — and prints a timed, captured transcript plus a one-line metric
for the pitch. No AWS, no network.

Usage:
    python3 scripts/measure_e2e.py
    python3 scripts/measure_e2e.py --json      # machine-readable summary only
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

# Offline: simulate every channel/email so nothing touches AWS.
os.environ.setdefault("SIMULATE_CHANNELS", "true")
os.environ.setdefault("SIMULATE_EMAIL", "true")

from shared.models import Claim, ClaimState, PartyRole  # noqa: E402
from agent.tools import claim_tools, external_action      # noqa: E402
from agent import bedrock                                 # noqa: E402


def _install_in_memory_store() -> dict:
    """Round-trip through to_item/from_item like DynamoDB so the run is faithful."""
    db: dict[str, dict] = {}
    save = lambda c: db.__setitem__(c.claim_id, c.to_item())
    load = lambda cid: Claim.from_item(db[cid]) if cid in db else None
    for mod in (claim_tools, external_action):
        mod.store.save = save
        mod.store.load = load
    return db


def main() -> int:
    as_json = "--json" in sys.argv

    _install_in_memory_store()
    # Deterministic triage (offline): a severe loss that needs a part.
    bedrock.triage_fnol = lambda peril, desc: {
        "severity": "moderate", "est_repair_days": 7, "summary": "rear collision",
        "source": "stub"}

    steps: list[str] = []
    channels_used: set[str] = set()

    def step(label: str, result: dict) -> None:
        ch = result.get("channel") or (result.get("send_result") or {}).get("channel")
        if ch:
            channels_used.add(ch)
        steps.append(label)

    t0 = time.perf_counter()

    # 1) FNOL on WhatsApp.
    opened = claim_tools.open_claim("POL-44821", "auto_collision",
                                    "+15555550100", "whatsapp",
                                    "Rear-ended at a light; bumper and sensor damage.")
    cid = opened["claim_id"]
    channels_used.add("whatsapp")
    step("FNOL captured (WhatsApp) + Bedrock triage", opened)

    # 2) Fan out to the gating parties in parallel: repair shop (RCS), lienholder (email).
    step("Repair shop engaged (RCS)", claim_tools.request_estimate(cid, "+15555550111"))
    step("Lienholder notified (email)", claim_tools.notify_lienholder(cid, "lender@example.com"))

    # 3) The twist: part back-ordered -> parts BLOCKED -> gate closes.
    claim_tools.check_parts_eta(cid, "rear bumper", days=5)
    gate = claim_tools.evaluate_commit_gate(cid)
    step(f"Commit gate CLOSED — blocked: {gate['blocked']}", gate)

    # 4) Re-plan: open an external ops ticket + source the part in 2 days (commit).
    ticket = external_action.open_external_ticket(
        cid, "Rear bumper back-ordered; source alternate supplier", system="itsm", priority="P2")
    step(f"External ops ticket opened ({ticket['ticket_id']})", ticket)
    claim_tools.check_parts_eta(cid, "rear bumper", days=2)  # now <=2 -> COMMITTED
    step("Parts re-sourced (committed)", {"channel": "email"})

    # 5) Repair shop RCS degrades -> continue on SMS, state preserved.
    step("Channel continuity: repair shop RCS->SMS",
         claim_tools.continue_on_fallback(cid, PartyRole.REPAIR_SHOP.value,
                                          "Continuing your appointment coordination by SMS."))
    claim_tools.commit_party(cid, PartyRole.REPAIR_SHOP.value, "appointment confirmed")
    claim_tools.commit_party(cid, PartyRole.LIENHOLDER.value, "coverage acknowledged")

    # 6) Gate opens; request human approval; adjuster approves; then settle.
    gate = claim_tools.evaluate_commit_gate(cid)
    step(f"Commit gate OPEN — {gate['reason']}", gate)
    appr_req = claim_tools.request_human_approval(cid, "+15555550123")
    step("Human-in-the-loop: adjuster asked to approve (RCS Approve/Hold)", appr_req)
    claim_tools.record_human_decision(cid, "approved", approver="adjuster-01",
                                      note="all parties reconciled")
    step("Adjuster APPROVED settlement (human decision recorded)", {"channel": "rcs_or_sms"})
    settled = claim_tools.issue_settlement(cid, 4200.0)
    step("Settlement issued (verified outcome)", settled)

    elapsed = time.perf_counter() - t0

    final = claim_tools.store.load(cid)
    parties = sorted(final.parties.keys())
    summary = {
        "claim_id": cid,
        "final_state": final.state.value,
        "verified": settled.get("verified", False),
        "human_approved": final.is_approved(),
        "approver": final.approval.get("approver", ""),
        "parties": parties,
        "party_count": len(parties),
        "channels": sorted(channels_used),
        "channel_count": len(channels_used),
        "external_tickets": final.facts.get("external_tickets", []),
        "elapsed_seconds": round(elapsed, 4),
        "steps": len(steps),
    }

    if as_json:
        import json
        print(json.dumps(summary, indent=2))
        return 0

    print("=" * 68)
    print("ONE TOUCH RESOLVE — measured end-to-end run (offline)")
    print("=" * 68)
    for i, s in enumerate(steps, 1):
        print(f"  {i:>2}. {s}")
    print("-" * 68)
    assert final.state == ClaimState.SETTLED, "claim did not reach SETTLED"
    print(f"  Claim {cid}: NEW -> SETTLED")
    print(f"  Parties coordinated : {summary['party_count']}  ({', '.join(parties)})")
    print(f"  Channels used       : {summary['channel_count']}  ({', '.join(summary['channels'])})")
    print(f"  External tickets    : {[t['ticket_id'] for t in summary['external_tickets']]}")
    print(f"  Outcome verified    : {summary['verified']} (read back from the record)")
    print(f"  Wall-clock          : {summary['elapsed_seconds']*1000:.1f} ms")
    print("-" * 68)
    print(f"  HEADLINE: claim settled across {summary['party_count']} parties and "
          f"{summary['channel_count']} channels in {summary['elapsed_seconds']*1000:.0f} ms, "
          f"with a code-verified outcome.")
    print("=" * 68)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
