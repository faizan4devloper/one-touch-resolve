"""Tests for multi-recipient email (SES) and the broadcast_message tool.

Covers:
  * ses_email.send_email accepting a single address (backward compatible),
    a list of To addresses, and optional Cc/Bcc.
  * claim_tools.broadcast_message fanning one message out to several parties,
    batching email recipients into a single SES send, routing phone parties
    individually, and reporting unknown roles as errors.

All offline: SIMULATE_EMAIL/SIMULATE_CHANNELS keep everything in-process.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from shared.models import Claim, ClaimState, Channel, Party, PartyRole, PartyStatus
from channels import ses_email
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


# --------------------------------------------------------------------------- #
# SES multi-recipient
# --------------------------------------------------------------------------- #
def test_send_email_single_address_backward_compatible():
    res = ses_email.send_email("one@example.com", "Subj", "Body")
    assert res["channel"] == "email"
    assert res["recipients"] == ["one@example.com"]
    assert res["recipient_count"] == 1


def test_send_email_multiple_to_plus_cc_bcc():
    res = ses_email.send_email(
        ["a@example.com", "b@example.com"], "Subj", "Body",
        cc="c@example.com", bcc=["d@example.com", "e@example.com"],
    )
    assert res["recipients"] == ["a@example.com", "b@example.com"]
    assert res["cc"] == ["c@example.com"]
    assert res["bcc"] == ["d@example.com", "e@example.com"]
    assert res["recipient_count"] == 5


def test_send_email_blank_entries_dropped_and_requires_a_recipient():
    res = ses_email.send_email(["x@example.com", "", "  "], "S", "B")
    assert res["recipients"] == ["x@example.com"]
    with pytest.raises(ValueError):
        ses_email.send_email([], "S", "B")


# --------------------------------------------------------------------------- #
# broadcast_message
# --------------------------------------------------------------------------- #
def _claim_with_parties():
    cid = claim_tools.open_claim("POL-BC", "auto_collision", "+15555550100")["claim_id"]
    # Repair shop on RCS (phone), lienholder + parts on email.
    claim_tools.engage_party(cid, PartyRole.REPAIR_SHOP.value, "+15555550111",
                             Channel.RCS.value, "estimate?")
    claim_tools.notify_lienholder(cid, "lender@example.com")
    claim = claim_tools.store.load(cid)
    claim.add_party(Party(role=PartyRole.PARTS_SUPPLIER, contact="parts@example.com",
                          preferred_channel=Channel.EMAIL, status=PartyStatus.NOTIFIED))
    claim_tools.store.save(claim)
    return cid


def test_broadcast_fans_out_to_multiple_parties():
    cid = _claim_with_parties()
    out = claim_tools.broadcast_message(
        cid,
        [PartyRole.REPAIR_SHOP.value, PartyRole.LIENHOLDER.value, PartyRole.PARTS_SUPPLIER.value],
        "Schedule update: appointment moved to Thursday.",
    )
    assert set(out["notified"]) == {
        PartyRole.REPAIR_SHOP.value, PartyRole.LIENHOLDER.value, PartyRole.PARTS_SUPPLIER.value}
    # Repair shop went out on its own (RCS) channel.
    assert out["results"][PartyRole.REPAIR_SHOP.value]["channel"] == Channel.RCS.value
    # The two email parties were batched into ONE SES send (same message id).
    lien = out["results"][PartyRole.LIENHOLDER.value]["result"]
    parts = out["results"][PartyRole.PARTS_SUPPLIER.value]["result"]
    assert lien["messageId"] == parts["messageId"]
    assert lien["recipient_count"] == 2
    assert set(lien["recipients"]) == {"lender@example.com", "parts@example.com"}


def test_broadcast_unknown_role_reported_not_fatal():
    cid = _claim_with_parties()
    out = claim_tools.broadcast_message(
        cid, [PartyRole.LIENHOLDER.value, "rental_provider"], "Heads up.")
    assert PartyRole.LIENHOLDER.value in out["notified"]
    assert "rental_provider" in out["errors"]


def test_broadcast_channel_override_routes_all_the_same_way():
    cid = _claim_with_parties()
    out = claim_tools.broadcast_message(
        cid, [PartyRole.REPAIR_SHOP.value, PartyRole.LIENHOLDER.value],
        "Reach everyone by SMS.", channel=Channel.SMS.value)
    for role in (PartyRole.REPAIR_SHOP.value, PartyRole.LIENHOLDER.value):
        assert out["results"][role]["channel"] == Channel.SMS.value
