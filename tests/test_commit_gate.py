"""Unit tests for the shared claim model and the commit gate."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from shared.models import (
    Channel, Claim, ClaimState, InvalidTransition, Party, PartyRole, PartyStatus,
)
from agent import commit_gate


def _claim_with_parties():
    claim = Claim.new("POL-1", "auto_collision")
    claim.transition(ClaimState.FNOL_CAPTURED)
    claim.add_party(Party(PartyRole.CLAIMANT, "+1", Channel.WHATSAPP,
                          required_for_commit=False, status=PartyStatus.COMMITTED))
    claim.add_party(Party(PartyRole.REPAIR_SHOP, "+2", Channel.RCS))
    claim.add_party(Party(PartyRole.PARTS_SUPPLIER, "p@x", Channel.EMAIL))
    claim.transition(ClaimState.PARTIES_ENGAGED)
    return claim


def test_state_machine_forward_ok():
    claim = Claim.new("POL", "peril")
    claim.transition(ClaimState.FNOL_CAPTURED)
    claim.transition(ClaimState.PARTIES_ENGAGED)
    assert claim.state == ClaimState.PARTIES_ENGAGED


def test_state_machine_illegal_skip():
    claim = Claim.new("POL", "peril")
    with pytest.raises(InvalidTransition):
        claim.transition(ClaimState.SETTLED)


def test_gate_closed_when_pending():
    claim = _claim_with_parties()
    decision = commit_gate.evaluate(claim)
    assert not decision.can_commit
    assert "repair_shop" in decision.pending or "parts_supplier" in decision.pending


def test_gate_closed_when_blocked_triggers_replan_signal():
    claim = _claim_with_parties()
    claim.set_party_status(PartyRole.PARTS_SUPPLIER, PartyStatus.BLOCKED, "back-ordered")
    claim.set_party_status(PartyRole.REPAIR_SHOP, PartyStatus.COMMITTED)
    decision = commit_gate.evaluate(claim)
    assert not decision.can_commit
    assert "parts_supplier" in decision.blocked


def test_gate_opens_when_all_committed():
    claim = _claim_with_parties()
    claim.set_party_status(PartyRole.REPAIR_SHOP, PartyStatus.COMMITTED)
    claim.set_party_status(PartyRole.PARTS_SUPPLIER, PartyStatus.COMMITTED)
    decision = commit_gate.try_commit(claim)
    assert decision.can_commit
    assert claim.state == ClaimState.COMMITTED


def test_claim_roundtrip_serialization():
    claim = _claim_with_parties()
    claim.facts["severity"] = "moderate"
    restored = Claim.from_item(claim.to_item())
    assert restored.claim_id == claim.claim_id
    assert restored.state == claim.state
    assert restored.parties.keys() == claim.parties.keys()
    assert restored.facts["severity"] == "moderate"
