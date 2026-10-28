"""Agent tools — the coordination actions the supervisor and sub-agents can take.

Each function is written as a plain Python callable with a clear docstring and
typed signature so it can be registered directly as a Strands ``@tool`` (see
``agent/supervisor.py``) or invoked from a Lambda. They operate on the shared
:class:`~shared.models.Claim` via the persistence layer and emit messages through
the channel router.

Keeping the tools free of Strands-specific decorators here means they are equally
usable from unit tests and from the AgentCore runtime.
"""

from __future__ import annotations

from typing import Any, Optional

from shared.models import Channel, Claim, ClaimState, Party, PartyRole, PartyStatus
from shared import store
from channels.router import route_message
from agent import commit_gate
from agent import bedrock
from agent import safety


# --------------------------------------------------------------------------- #
# Claim lifecycle
# --------------------------------------------------------------------------- #
def open_claim(policy_number: str, peril: str, claimant_contact: str,
               claimant_channel: str = "whatsapp",
               description: str = "") -> dict[str, Any]:
    """Open a new claim at FNOL and register the claimant.

    The loss is triaged by a real Amazon Bedrock model (severity, estimated
    repair days, summary). Returns the new claim_id + state.
    """
    claim = Claim.new(policy_number=policy_number, peril=peril)
    claim.transition(ClaimState.FNOL_CAPTURED)

    triage = bedrock.triage_fnol(peril, description or peril)
    claim.facts["severity"] = triage.get("severity", "moderate")
    claim.facts["est_repair_days"] = triage.get("est_repair_days", 7)
    claim.facts["triage_summary"] = triage.get("summary", "")
    claim.facts["triage_source"] = triage.get("source", "bedrock")

    claim.add_party(
        Party(
            role=PartyRole.CLAIMANT,
            contact=claimant_contact,
            preferred_channel=Channel(claimant_channel),
            required_for_commit=False,
            status=PartyStatus.COMMITTED,
        )
    )
    claim.log(f"FNOL captured for policy {policy_number}, peril={peril} "
              f"[triage:{claim.facts['triage_source']} · {claim.facts['severity']} · "
              f"{claim.facts['est_repair_days']}d]")
    store.save(claim)
    return {"claim_id": claim.claim_id, "state": claim.state.value,
            "triage": triage}


def record_fact(claim_id: str, key: str, value: Any) -> dict[str, Any]:
    """Record a structured fact on the claim (e.g. severity, part ETA, timeline)."""
    claim = _require(claim_id)
    claim.facts[key] = value
    claim.log(f"fact recorded: {key}={value}")
    store.save(claim)
    return {"claim_id": claim_id, "facts": claim.facts}


# --------------------------------------------------------------------------- #
# Party engagement (fan-out)
# --------------------------------------------------------------------------- #
def engage_party(claim_id: str, role: str, contact: str, channel: str,
                 message: str, required: bool = True,
                 options: Optional[list[str]] = None) -> dict[str, Any]:
    """Engage an external party on their channel and mark them NOTIFIED.

    This is the fan-out step: e.g. request an estimate from the repair shop over
    RCS/SMS, or notify the lienholder over email. Moves the claim into
    PARTIES_ENGAGED the first time a gating party is engaged.
    """
    claim = _require(claim_id)
    party_role = PartyRole(role)
    ch = Channel(channel)

    claim.add_party(
        Party(
            role=party_role,
            contact=contact,
            preferred_channel=ch,
            required_for_commit=required,
            status=PartyStatus.NOTIFIED,
        )
    )

    subject = f"Claim {claim_id} — action needed" if ch == Channel.EMAIL else None
    result = route_message(ch, contact, message, subject=subject, rcs_options=options)

    if claim.state == ClaimState.FNOL_CAPTURED and required:
        claim.transition(ClaimState.PARTIES_ENGAGED)
    claim.log(f"engaged {role} on {channel}")
    store.save(claim)
    return {"claim_id": claim_id, "role": role, "send_result": result,
            "state": claim.state.value}


def request_estimate(claim_id: str, repair_shop_contact: str,
                     channel: str = "rcs") -> dict[str, Any]:
    """Ask the repair shop for a repair estimate + earliest appointment (RCS card)."""
    message = (f"Repair estimate requested for claim {claim_id}. "
               f"Please confirm earliest appointment and parts needed.")
    return engage_party(
        claim_id, PartyRole.REPAIR_SHOP.value, repair_shop_contact, channel,
        message, required=True, options=["This week", "Next week", "Need parts first"],
    )


def check_parts_eta(claim_id: str, part: str, days: int,
                    supplier_contact: str = "parts@example.com") -> dict[str, Any]:
    """Record a parts ETA from the supplier and mark the parts party accordingly.

    If the part is available soon (<= 2 days) the supplier is COMMITTED; a longer
    back-order marks it BLOCKED, which will force the supervisor to re-plan
    (e.g. offer a rental) via the commit gate.
    """
    claim = _require(claim_id)
    if PartyRole.PARTS_SUPPLIER.value not in claim.parties:
        claim.add_party(Party(role=PartyRole.PARTS_SUPPLIER, contact=supplier_contact,
                              preferred_channel=Channel.EMAIL, required_for_commit=True))
    claim.facts["part"] = part
    claim.facts["part_eta_days"] = days

    if days <= 2:
        claim.set_party_status(PartyRole.PARTS_SUPPLIER, PartyStatus.COMMITTED,
                               note=f"{part} available in {days}d")
    else:
        claim.set_party_status(PartyRole.PARTS_SUPPLIER, PartyStatus.BLOCKED,
                               note=f"{part} back-ordered {days}d")
    store.save(claim)
    return {"claim_id": claim_id, "part": part, "eta_days": days,
            "parts_status": claim.parties[PartyRole.PARTS_SUPPLIER.value].status.value}


def notify_lienholder(claim_id: str, lienholder_email: str) -> dict[str, Any]:
    """Send the lienholder a formal coverage notice via SES (durable/auditable)."""
    claim = _require(claim_id)
    body = (f"This notice confirms an open claim {claim_id} on policy "
            f"{claim.policy_number}. Coverage and settlement details will follow.")
    return engage_party(claim_id, PartyRole.LIENHOLDER.value, lienholder_email,
                        Channel.EMAIL.value, body, required=True)


def commit_party(claim_id: str, role: str, note: str = "") -> dict[str, Any]:
    """Mark a party as COMMITTED (e.g. repair shop confirmed the appointment)."""
    claim = _require(claim_id)
    claim.set_party_status(PartyRole(role), PartyStatus.COMMITTED, note=note)
    store.save(claim)
    return {"claim_id": claim_id, "role": role, "status": "committed"}


# --------------------------------------------------------------------------- #
# Commit gate + settlement
# --------------------------------------------------------------------------- #
def evaluate_commit_gate(claim_id: str) -> dict[str, Any]:
    """Check whether all required parties have committed; advance if so.

    This is the multi-party gate. When it opens, the claim advances to COMMITTED.
    When it is closed by a BLOCKED party, the response names who to re-plan around.

    The gate is a pure function of party statuses: calling it again without
    changing any party's status returns the same result. To make the
    orchestration robust against a model that re-polls the gate, we fingerprint
    the party-status set and short-circuit after repeated no-change calls,
    returning a terminal ``looping`` signal instructing the caller to re-plan or
    stop rather than evaluate again.
    """
    claim = _require(claim_id)

    # Fingerprint current party statuses (what the gate decision depends on).
    fingerprint = ";".join(
        f"{role}:{p.status.value}"
        for role, p in sorted(claim.parties.items())
    )
    prev_fp = claim.facts.get("_gate_fp")
    repeat = int(claim.facts.get("_gate_repeat", 0))
    repeat = repeat + 1 if fingerprint == prev_fp else 0
    claim.facts["_gate_fp"] = fingerprint
    claim.facts["_gate_repeat"] = repeat

    decision = commit_gate.try_commit(claim)

    # No state changed since the last evaluation and the gate is still closed:
    # stop the caller from polling. Surface an explicit terminal instruction.
    if repeat >= 1 and not decision.can_commit:
        store.save(claim)
        action = (
            "re-plan the blocked party with a state-changing tool "
            "(check_parts_eta with an expedited ETA, commit_party on an "
            "alternative, or engage_party for a replacement), then evaluate once"
            if decision.blocked
            else "wait for the pending party; do not evaluate again until a "
                 "party's status changes"
        )
        return {
            "claim_id": claim_id,
            "state": claim.state.value,
            "looping": True,
            "stop": True,
            "message": (
                "Commit gate unchanged since the last evaluation — re-evaluating "
                "will not change the result. Do NOT call evaluate_commit_gate "
                f"again. Next: {action}."
            ),
            **decision.to_dict(),
        }

    # Successful commit resets the loop guard for any later phase.
    if decision.can_commit:
        claim.facts.pop("_gate_fp", None)
        claim.facts.pop("_gate_repeat", None)

    store.save(claim)
    return {"claim_id": claim_id, "state": claim.state.value, **decision.to_dict()}


def request_human_approval(claim_id: str, adjuster_contact: str,
                           channel: str = "rcs") -> dict[str, Any]:
    """Request a human adjuster's sign-off before any settlement (money movement).

    Only valid once the multi-party commit gate has opened (claim is COMMITTED).
    Moves the claim to PENDING_APPROVAL and sends the adjuster an interactive
    RCS card with Approve / Hold choices (falls back to SMS/simulation). The
    settlement step refuses to run until a human records an ``approved`` decision
    — the "human stays in control" rule every 2026 claims guideline requires,
    enforced in code and in the state machine, not in prompt text.
    """
    claim = _require(claim_id)
    if claim.state != ClaimState.COMMITTED:
        return {"claim_id": claim_id,
                "error": "approval can only be requested once all parties have committed",
                "state": claim.state.value}

    # Register/refresh the adjuster party so the decision has an owner on record.
    claim.add_party(Party(role=PartyRole.ADJUSTER, contact=adjuster_contact,
                          preferred_channel=Channel(channel),
                          required_for_commit=False, status=PartyStatus.NOTIFIED))
    claim.request_approval(approver=adjuster_contact)

    amount = claim.facts.get("settlement_amount")
    title = f"Approval needed — claim {claim_id}"
    desc = ("All parties have committed. Approve to release the settlement"
            + (f" of ${amount:,.2f}" if isinstance(amount, (int, float)) else "")
            + ", or Hold to review.")
    result = route_message(Channel(channel), adjuster_contact, desc,
                           subject=title, rcs_options=["Approve", "Hold"])
    store.save(claim)
    return {"claim_id": claim_id, "state": claim.state.value,
            "approval": claim.approval, "send_result": result}


def record_human_decision(claim_id: str, decision: str, approver: str = "",
                          note: str = "") -> dict[str, Any]:
    """Record the adjuster's decision on a PENDING_APPROVAL claim.

    ``decision`` is one of ``approved`` | ``held`` | ``denied``. ``approved``
    unlocks settlement; ``held``/``denied`` return the claim to COMMITTED so the
    supervisor can address the concern and re-request approval.
    """
    claim = _require(claim_id)
    if claim.state != ClaimState.PENDING_APPROVAL:
        return {"claim_id": claim_id,
                "error": "no approval is pending for this claim",
                "state": claim.state.value}
    try:
        claim.record_decision(decision, approver=approver, note=note)
    except ValueError as e:
        return {"claim_id": claim_id, "error": str(e), "state": claim.state.value}
    store.save(claim)
    return {"claim_id": claim_id, "state": claim.state.value,
            "approved": claim.is_approved(), "approval": claim.approval}


def issue_settlement(claim_id: str, amount: float,
                     claimant_channel: str = "whatsapp") -> dict[str, Any]:
    """Issue the settlement: email the settlement letter (SES) and notify the
    claimant on their channel. Requires the claim to be COMMITTED **and**
    human-approved (PENDING_APPROVAL with an ``approved`` decision)."""
    claim = _require(claim_id)
    # Code-enforced human-in-the-loop: no money moves without an explicit human
    # approval. This is checked here (not left to the model) and mirrors the
    # verified_outcome discipline — the agent cannot talk its way past it.
    if claim.state != ClaimState.PENDING_APPROVAL or not claim.is_approved():
        return {"claim_id": claim_id,
                "error": "settlement requires a human approval decision",
                "state": claim.state.value,
                "approval": claim.approval.get("decision", "none")}

    claimant = claim.parties[PartyRole.CLAIMANT.value]
    # Formal settlement letter via SES to the lienholder if present.
    lien = claim.parties.get(PartyRole.LIENHOLDER.value)
    if lien:
        route_message(Channel.EMAIL, lien.contact,
                      f"Settlement of ${amount:,.2f} approved for claim {claim_id}.",
                      subject=f"Settlement letter — claim {claim_id}")

    # Claimant notification on their preferred channel.
    route_message(Channel(claimant_channel), claimant.contact,
                  f"Good news — your claim {claim_id} is settled for ${amount:,.2f}.")

    claim.facts["settlement_amount"] = amount
    claim.transition(ClaimState.SETTLED)
    claim.log(f"settled for ${amount:,.2f}")
    store.save(claim)
    # Read back and author the outcome in code: if the write did not land as
    # SETTLED, verified_outcome raises and the agent never reports success.
    return safety.verified_outcome(
        claim_id, ClaimState.SETTLED.value, store.load,
        say=f"Claim {claim_id} is settled for ${amount:,.2f}.",
        amount=amount,
    )


# --------------------------------------------------------------------------- #
# Generic messaging + continuity
# --------------------------------------------------------------------------- #
def send_message(claim_id: str, role: str, body: str,
                 channel: Optional[str] = None) -> dict[str, Any]:
    """Send an ad-hoc message to a party. If ``channel`` is omitted, the party's
    preferred channel is used — enabling channel-aware continuity."""
    claim = _require(claim_id)
    party = claim.parties[PartyRole(role).value]
    ch = Channel(channel) if channel else party.preferred_channel
    subject = f"Claim {claim_id} update" if ch == Channel.EMAIL else None
    result = route_message(ch, party.contact, body, subject=subject)
    claim.log(f"message to {role} on {ch.value}")
    store.save(claim)
    return {"claim_id": claim_id, "role": role, "channel": ch.value, "result": result}


def continue_on_fallback(claim_id: str, role: str, body: str) -> dict[str, Any]:
    """Continue the SAME workflow on SMS when a party's RCS session degrades.

    Demonstrates channel-aware continuity: the claim state is untouched; only the
    transport changes. The party keeps their context because state lives in the
    claim record + AgentCore Memory, never in the channel.
    """
    claim = _require(claim_id)
    party = claim.parties[PartyRole(role).value]
    party.preferred_channel = Channel.SMS
    claim.log(f"channel continuity: {role} RCS→SMS fallback, state preserved")
    store.save(claim)
    result = route_message(Channel.SMS, party.contact, body)
    return {"claim_id": claim_id, "role": role, "channel": "sms",
            "continuity": True, "result": result}


# --------------------------------------------------------------------------- #
def _require(claim_id: str) -> Claim:
    claim = store.load(claim_id)
    if claim is None:
        raise KeyError(f"claim {claim_id} not found")
    return claim
