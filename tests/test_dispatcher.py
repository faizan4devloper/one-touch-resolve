"""Dispatcher tests: SNS record normalization + duplicate-skip + agent invoke.

The dispatcher routes raw SNS messages to the right channel parser, de-dupes on
the inbound message id, and invokes the agent. We stub dedupe and the agent so
the routing/normalization logic is tested in isolation.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from channels import dispatcher


@pytest.fixture
def seen(monkeypatch):
    processed = []
    ids = set()

    def mark_if_new(mid):
        if mid in ids:
            return False
        ids.add(mid)
        return True

    monkeypatch.setattr(dispatcher.dedupe, "mark_if_new", mark_if_new)
    monkeypatch.setattr(dispatcher, "_invoke_agent",
                        lambda ev: processed.append(ev) or {"handled": True, "actor": ev.get("from")})
    # WhatsApp media persistence is best-effort; skip it in unit tests.
    monkeypatch.setattr(dispatcher, "_persist_media", lambda ev: ev)
    return processed


def _sns_event(message: dict) -> dict:
    return {"Records": [{"Sns": {"Message": json.dumps(message)}}]}


def test_eum_sms_rcs_message_normalized(seen):
    event = _sns_event({
        "originationNumber": "+15555550100", "destinationNumber": "+15555550111",
        "messageBody": "This week", "inboundMessageId": "m-1",
    })
    dispatcher.lambda_handler(event)
    assert len(seen) == 1
    assert seen[0]["channel"] == "sms_rcs"
    assert seen[0]["from"] == "+15555550100"
    assert seen[0]["body"] == "This week"


def test_whatsapp_message_normalized(seen):
    event = _sns_event({
        "from": "+15555550100", "messageId": "m-2",
        "message": {"text": "Photo sent"},
    })
    dispatcher.lambda_handler(event)
    assert len(seen) == 1
    assert seen[0]["channel"] == "whatsapp"
    assert seen[0]["from"] == "+15555550100"
    assert seen[0]["body"] == "Photo sent"


def test_duplicate_message_skipped(seen):
    msg = {"originationNumber": "+1", "destinationNumber": "+2",
           "messageBody": "x", "inboundMessageId": "dup"}
    event = {"Records": [
        {"Sns": {"Message": json.dumps(msg)}},
        {"Sns": {"Message": json.dumps(msg)}},
    ]}
    resp = dispatcher.lambda_handler(event)
    assert len(seen) == 1  # second record de-duped
    assert any("skipped_duplicate" in r for r in resp["results"])


def test_malformed_sns_body_does_not_crash(seen):
    event = {"Records": [{"Sns": {"Message": "not-json"}}]}
    resp = dispatcher.lambda_handler(event)
    assert resp["statusCode"] == 200
