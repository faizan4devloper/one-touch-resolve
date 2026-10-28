"""ZCAA state-machine tests — the zero-call accident journey.

Drives sessions through start_session -> respond() taps, covering the safe and
not-safe branches, the drivable (repair) vs not-drivable (tow) split, and the
consent/authorization audit trail. Bedrock triage, tow-ETA and SES email are
stubbed so the state machine is tested deterministically and offline.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from zcaa import session as z
from zcaa.session import Step


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    # Reset the module session store between tests.
    z._SESSIONS.clear()
    # Stub integrations that would hit AWS.
    monkeypatch.setattr(z, "_send_email", lambda *a, **k: {"messageId": "sim"})
    monkeypatch.setattr(z, "_tow_eta_minutes", lambda *a, **k: 20)
    monkeypatch.setattr(z, "_remember", lambda *a, **k: None)


def _triage(drivable):
    sev = "minor" if drivable else "severe"
    return lambda peril, desc: {"severity": sev, "est_repair_days": 3 if drivable else 21,
                                "source": "stub", "drivable": drivable}


def _start():
    return z.start_session(customer_name="Alex Rivera", policy_number="HO-1",
                           location="Main St", vehicle="Tesla", phone="+15555550100")


def test_start_opens_with_safety_check():
    sess = _start()
    assert sess.step == Step.SAFETY_CHECK
    assert sess.awaiting is True
    assert sess.messages[-1].choices  # Yes/No buttons present


def test_safe_drivable_path_reaches_repair_then_done(monkeypatch):
    monkeypatch.setattr(z, "_triage", _triage(drivable=True))
    sess = _start()
    z.respond(sess.session_id, "Yes, I'm safe")       # -> DAMAGE_MEDIA
    assert sess.step == Step.DAMAGE_MEDIA
    z.respond(sess.session_id, "Photo sent")           # triage -> REPAIR_OFFER (drivable)
    assert sess.step == Step.REPAIR_OFFER
    z.respond(sess.session_id, "Yes, book repair")     # -> SUMMARY
    assert sess.step == Step.SUMMARY
    z.respond(sess.session_id, "Great, thanks")        # -> DONE (+ summary email)
    assert sess.step == Step.DONE
    assert "repair" in sess.facts


def test_not_drivable_path_offers_tow_then_rental(monkeypatch):
    monkeypatch.setattr(z, "_triage", _triage(drivable=False))
    sess = _start()
    z.respond(sess.session_id, "Yes, I'm safe")        # -> DAMAGE_MEDIA
    z.respond(sess.session_id, "Photo sent")           # triage -> TOW_OFFER (not drivable)
    assert sess.step == Step.TOW_OFFER
    z.respond(sess.session_id, "Yes, send a tow")      # -> RENTAL_OFFER, tow dispatched
    assert sess.step == Step.RENTAL_OFFER
    assert sess.facts["tow"]["eta_min"] == 20
    z.respond(sess.session_id, "Yes, arrange rental")  # -> REPAIR_OFFER
    assert sess.step == Step.REPAIR_OFFER
    assert "rental" in sess.facts


def test_not_safe_routes_through_medical(monkeypatch):
    monkeypatch.setattr(z, "_triage", _triage(drivable=True))
    sess = _start()
    z.respond(sess.session_id, "No, I need help")      # -> MEDICAL
    assert sess.step == Step.MEDICAL
    assert sess.facts["safety"] == "assisted"
    z.respond(sess.session_id, "We're okay now")        # -> DAMAGE_MEDIA
    assert sess.step == Step.DAMAGE_MEDIA


def test_every_tap_is_recorded_as_consent(monkeypatch):
    monkeypatch.setattr(z, "_triage", _triage(drivable=True))
    sess = _start()
    z.respond(sess.session_id, "Yes, I'm safe")
    z.respond(sess.session_id, "Photo sent")
    # Each answered tap is an authorization record.
    consents = sess.facts.get("consents", [])
    assert len(consents) >= 2
    assert all("answer" in c and "ts" in c for c in consents)


def test_respond_ignores_input_when_not_awaiting(monkeypatch):
    monkeypatch.setattr(z, "_triage", _triage(drivable=True))
    sess = _start()
    sess.awaiting = False
    before = len(sess.messages)
    z.respond(sess.session_id, "random")
    assert len(sess.messages) == before  # nothing recorded


def test_unknown_session_raises():
    with pytest.raises(KeyError):
        z.respond("ZCAA-NOPE", "hi")
