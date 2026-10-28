"""Tests for the agent claim tools (open_claim -> engage -> commit -> settle).

The tools are exercised end-to-end against an in-memory claim store and simulated
channels, so the whole coordination lifecycle runs offline with no AWS. Bedrock
triage is stubbed to keep the test deterministic (triage itself is covered by the
bedrock parse tests).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from shared.models import Claim, ClaimState, PartyRole, PartyStatus
from agent.tools import claim_tools
from agent import bedrock


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    # Simulated channels so route_message never touches AWS.
    monkeypatch.setenv("SIMULATE_CHANNELS", "true")
    monkeypatch.setenv("SIMULATE_EMAIL", "true")

    # In-memory claim store shared by the tools under test.
    db: dict[str, Claim] = {}
    monkeypatch.setattr(claim_tools.store, "save", lambda c: db.__setitem__(c.claim_id, c))
    monkeypatch.setattr(claim_tools.store, "load", lambda cid: db.get(cid))

    # Deterministic triage (no model call).
    monkeypatch.setattr(bedrock, "triage_fnol", lambda peril, desc: {
        "severity": "moderate", "est_repair_days": 7, "summary": "stub", "source": "stub"})
    return db


def test_open_claim_captures_fnol_and_registers_claimant():
    out = claim_tools.open_claim("POL-1", "auto_collision", "+15555550100", "whatsapp", "rear-ended")
    assert out["state"] == ClaimState.FNOL_CAPTURED.value
    claim = claim_tools.store.load(out["claim_id"])
    assert PartyRole.CLAIMANT.value in claim.parties
    # Claimant is pre-committed and NOT a gating party.
    claimant = claim.parties[PartyRole.CLAIMANT.value]
    assert claimant.required_for_commit is False
    assert claim.facts["severity"] == "moderate"


def test_full_lifecycle_new_to_settled():
    cid = claim_tools.open_claim("POL-9", "auto_collision", "+15555550100")["claim_id"]

    # Engage the two gating parties.
    claim_tools.request_estimate(cid, "+15555550111")                  # repair shop (RCS)
    claim_tools.notify_lienholder(cid, "lien@example.com")             # lienholder (email)

    # Gate must be CLOSED while parties are only NOTIFIED.
    gate = claim_tools.evaluate_commit_gate(cid)
    assert gate["can_commit"] is False
    assert gate["pending"]

    # Commit both.
    claim_tools.commit_party(cid, PartyRole.REPAIR_SHOP.value, "booked")
    claim_tools.commit_party(cid, PartyRole.LIENHOLDER.value, "ack")

    gate = claim_tools.evaluate_commit_gate(cid)
    assert gate["can_commit"] is True
    assert gate["state"] == ClaimState.COMMITTED.value

    # Human-in-the-loop: settlement must not proceed without a human decision.
    blocked = claim_tools.issue_settlement(cid, 4200.0)
    assert "error" in blocked
    assert blocked["state"] != ClaimState.SETTLED.value

    # Adjuster is asked to sign off, then approves.
    req = claim_tools.request_human_approval(cid, "+15555550123")
    assert req["state"] == ClaimState.PENDING_APPROVAL.value
    dec = claim_tools.record_human_decision(cid, "approved", approver="adj-1")
    assert dec["approved"] is True

    settled = claim_tools.issue_settlement(cid, 4200.0)
    assert settled["state"] == ClaimState.SETTLED.value
    assert settled["amount"] == 4200.0


def test_parts_backorder_blocks_the_gate():
    cid = claim_tools.open_claim("POL-7", "auto_collision", "+15555550100")["claim_id"]
    claim_tools.request_estimate(cid, "+15555550111")
    claim_tools.commit_party(cid, PartyRole.REPAIR_SHOP.value)
    # Long ETA -> parts supplier BLOCKED.
    res = claim_tools.check_parts_eta(cid, "bumper", days=10)
    assert res["parts_status"] == PartyStatus.BLOCKED.value

    gate = claim_tools.evaluate_commit_gate(cid)
    assert gate["can_commit"] is False
    assert PartyRole.PARTS_SUPPLIER.value in gate["blocked"]


def test_settlement_rejected_before_committed():
    cid = claim_tools.open_claim("POL-3", "auto_collision", "+15555550100")["claim_id"]
    out = claim_tools.issue_settlement(cid, 1000.0)
    assert "error" in out
    assert out["state"] != ClaimState.SETTLED.value


def test_continue_on_fallback_switches_channel_preserves_state():
    cid = claim_tools.open_claim("POL-5", "auto_collision", "+15555550100")["claim_id"]
    claim_tools.request_estimate(cid, "+15555550111")
    before = claim_tools.store.load(cid).state
    res = claim_tools.continue_on_fallback(cid, PartyRole.REPAIR_SHOP.value, "continuing on SMS")
    assert res["continuity"] is True and res["channel"] == "sms"
    # State is untouched by a channel switch.
    assert claim_tools.store.load(cid).state == before
