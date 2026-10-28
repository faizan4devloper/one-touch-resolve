"""Tests for the agent-safety invariants (agent/safety.py + its use in tools).

Proves:
  * a failed/mismatched write is never reported as a successful outcome;
  * a verified write yields a code-authored 'say' sentence;
  * identity is pinned to the trusted id regardless of model-supplied args;
  * issue_settlement raises rather than claiming SETTLED if persistence is lost.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from shared.models import Claim, ClaimState, PartyRole
from agent import safety, bedrock
from agent.tools import claim_tools


def test_verified_outcome_passes_when_state_matches():
    claim = Claim.new("POL", "auto_collision")
    claim.transition(ClaimState.FNOL_CAPTURED)
    out = safety.verified_outcome(
        claim.claim_id, ClaimState.FNOL_CAPTURED.value,
        reload_fn=lambda cid: claim, say="ok")
    assert out["verified"] is True and out["say"] == "ok"


def test_verified_outcome_raises_when_record_missing():
    with pytest.raises(safety.OutcomeNotVerified):
        safety.verified_outcome("CLM-X", ClaimState.SETTLED.value,
                                reload_fn=lambda cid: None, say="should not surface")


def test_verified_outcome_raises_on_state_mismatch():
    claim = Claim.new("POL", "auto_collision")  # state NEW
    with pytest.raises(safety.OutcomeNotVerified):
        safety.verified_outcome(claim.claim_id, ClaimState.SETTLED.value,
                                reload_fn=lambda cid: claim, say="nope")


def test_pin_actor_overrides_model_supplied_id():
    args = safety.pin_actor({"actor_id": "attacker", "x": 1}, "trusted-123")
    assert args["actor_id"] == "trusted-123" and args["x"] == 1


def test_pin_actor_noop_without_trusted_id():
    args = safety.pin_actor({"actor_id": "keep"}, "")
    assert args["actor_id"] == "keep"


def test_issue_settlement_does_not_report_done_if_write_lost(monkeypatch):
    """If persistence silently fails (read-back finds nothing), the tool must
    raise, not return a SETTLED outcome."""
    monkeypatch.setenv("SIMULATE_CHANNELS", "true")
    monkeypatch.setenv("SIMULATE_EMAIL", "true")
    monkeypatch.setattr(bedrock, "triage_fnol", lambda p, d: {
        "severity": "moderate", "est_repair_days": 7, "summary": "s", "source": "stub"})

    db: dict[str, dict] = {}
    # Serialize on save (like DynamoDB) so a no-op save genuinely loses the write.
    monkeypatch.setattr(claim_tools.store, "save", lambda c: db.__setitem__(c.claim_id, c.to_item()))
    monkeypatch.setattr(claim_tools.store, "load",
                        lambda cid: Claim.from_item(db[cid]) if cid in db else None)

    cid = claim_tools.open_claim("POL", "auto_collision", "+15555550100")["claim_id"]
    claim_tools.request_estimate(cid, "+15555550111")
    claim_tools.notify_lienholder(cid, "lien@example.com")
    claim_tools.commit_party(cid, PartyRole.REPAIR_SHOP.value)
    claim_tools.commit_party(cid, PartyRole.LIENHOLDER.value)
    claim_tools.evaluate_commit_gate(cid)
    # Pass the human-in-the-loop gate so settlement is reachable.
    claim_tools.request_human_approval(cid, "+15555550123")
    claim_tools.record_human_decision(cid, "approved", approver="adj-1")

    # Simulate persistence loss on the final write: save becomes a no-op, so the
    # read-back in verified_outcome still sees PENDING_APPROVAL, not SETTLED.
    monkeypatch.setattr(claim_tools.store, "save", lambda c: None)
    with pytest.raises(safety.OutcomeNotVerified):
        claim_tools.issue_settlement(cid, 4200.0)
