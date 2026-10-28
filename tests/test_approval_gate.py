"""Tests for the human-in-the-loop approval gate before settlement.

The gate is the 2026 governance guarantee: no money moves without an explicit
human decision. It is enforced in TWO places that can't be talked around by the
model — the claim state machine (SETTLED is only reachable from PENDING_APPROVAL)
and ``issue_settlement`` (refuses unless ``is_approved``). These tests cover the
approve path, the hold/deny kickback path, and the refuse-without-approval path.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from shared.models import Claim, ClaimState, PartyRole
from agent.tools import claim_tools
from agent import bedrock


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    monkeypatch.setenv("SIMULATE_CHANNELS", "true")
    monkeypatch.setenv("SIMULATE_EMAIL", "true")
    db: dict[str, Claim] = {}
    monkeypatch.setattr(claim_tools.store, "save", lambda c: db.__setitem__(c.claim_id, c))
    monkeypatch.setattr(claim_tools.store, "load", lambda cid: db.get(cid))
    monkeypatch.setattr(bedrock, "triage_fnol", lambda peril, desc: {
        "severity": "moderate", "est_repair_days": 7, "summary": "stub", "source": "stub"})
    return db


def _committed_claim() -> str:
    """Open a claim and drive it to COMMITTED (gate open), ready for approval."""
    cid = claim_tools.open_claim("POL-APPR", "auto_collision", "+15555550100")["claim_id"]
    claim_tools.request_estimate(cid, "+15555550111")
    claim_tools.notify_lienholder(cid, "lien@example.com")
    claim_tools.commit_party(cid, PartyRole.REPAIR_SHOP.value, "booked")
    claim_tools.commit_party(cid, PartyRole.LIENHOLDER.value, "ack")
    gate = claim_tools.evaluate_commit_gate(cid)
    assert gate["state"] == ClaimState.COMMITTED.value
    return cid


def test_settlement_refused_without_approval():
    cid = _committed_claim()
    out = claim_tools.issue_settlement(cid, 4200.0)
    assert "error" in out
    assert out["state"] == ClaimState.COMMITTED.value
    # Nothing moved: still not settled.
    assert claim_tools.store.load(cid).state == ClaimState.COMMITTED


def test_approve_path_unlocks_settlement():
    cid = _committed_claim()
    req = claim_tools.request_human_approval(cid, "+15555550123")
    assert req["state"] == ClaimState.PENDING_APPROVAL.value

    # Still cannot settle while the decision is only 'pending'.
    assert "error" in claim_tools.issue_settlement(cid, 4200.0)

    dec = claim_tools.record_human_decision(cid, "approved", approver="adj-1", note="looks good")
    assert dec["approved"] is True

    settled = claim_tools.issue_settlement(cid, 4200.0)
    assert settled["state"] == ClaimState.SETTLED.value
    claim = claim_tools.store.load(cid)
    assert claim.approval["decision"] == "approved"
    assert claim.approval["approver"] == "adj-1"


def test_hold_path_kicks_back_to_committed():
    cid = _committed_claim()
    claim_tools.request_human_approval(cid, "+15555550123")
    dec = claim_tools.record_human_decision(cid, "held", approver="adj-1", note="verify photos")
    assert dec["approved"] is False
    # A held decision returns the claim to COMMITTED for a re-decision.
    assert claim_tools.store.load(cid).state == ClaimState.COMMITTED
    # And settlement is still refused.
    assert "error" in claim_tools.issue_settlement(cid, 4200.0)

    # Re-request + approve lets it through.
    claim_tools.request_human_approval(cid, "+15555550123")
    claim_tools.record_human_decision(cid, "approved", approver="adj-1")
    assert claim_tools.issue_settlement(cid, 4200.0)["state"] == ClaimState.SETTLED.value


def test_denied_decision_blocks_settlement():
    cid = _committed_claim()
    claim_tools.request_human_approval(cid, "+15555550123")
    claim_tools.record_human_decision(cid, "denied", approver="adj-1", note="fraud signal")
    assert claim_tools.store.load(cid).state == ClaimState.COMMITTED
    assert "error" in claim_tools.issue_settlement(cid, 4200.0)


def test_approval_cannot_be_requested_before_commit_gate_opens():
    cid = claim_tools.open_claim("POL-EARLY", "auto_collision", "+15555550100")["claim_id"]
    claim_tools.request_estimate(cid, "+15555550111")  # party only NOTIFIED -> gate closed
    out = claim_tools.request_human_approval(cid, "+15555550123")
    assert "error" in out
    assert out["state"] != ClaimState.PENDING_APPROVAL.value


def test_invalid_decision_rejected():
    cid = _committed_claim()
    claim_tools.request_human_approval(cid, "+15555550123")
    out = claim_tools.record_human_decision(cid, "maybe")
    assert "error" in out
    # State unchanged by an invalid decision.
    assert claim_tools.store.load(cid).state == ClaimState.PENDING_APPROVAL
