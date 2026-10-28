"""CDS payload-contract tests.

Every outbound send the engine makes is validated against the botocore service
model of the real AWS API — without sending anything. We capture the exact
kwargs each adapter passes to its boto3 client and run them through botocore's
ParamValidator for the corresponding operation. If AWS changes a required field,
or an adapter builds a malformed request, these fail in CI instead of at runtime.

This mirrors the discipline of validating against the live API contract, which a
single integration test against a mock cannot give.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import botocore.session
from botocore.validate import ParamValidator

from channels import eum_messaging, ses_email, whatsapp

_session = botocore.session.get_session()


def _validate(service: str, operation: str, params: dict) -> None:
    model = _session.get_service_model(service).operation_model(operation)
    report = ParamValidator().validate(params, model.input_shape)
    assert not report.has_errors(), report.generate_report()


class _Capture:
    """Stand-in boto3 client that records the kwargs of the first call."""

    def __init__(self):
        self.captured = {}

    def _record(self, name):
        def fn(**kwargs):
            self.captured[name] = kwargs
            # Return the minimal shape each adapter reads back.
            return {"MessageId": "mid-test", "messageId": "mid-test"}
        return fn

    def __getattr__(self, name):
        return self._record(name)


def _patch(monkeypatch, module, cap):
    monkeypatch.setattr(module, "_client", lambda *a, **k: cap)


def test_eum_send_text_matches_service_model(monkeypatch):
    cap = _Capture()
    _patch(monkeypatch, eum_messaging, cap)
    monkeypatch.setenv("EUM_ORIGINATION_IDENTITY", "pool-0123456789abcdef")
    monkeypatch.setenv("SIMULATE_CHANNELS", "false")
    eum_messaging.send_text("+12065550100", "Claim CLM-1 update", channel_hint="sms")
    _validate("pinpoint-sms-voice-v2", "SendTextMessage", cap.captured["send_text_message"])


def test_eum_rcs_card_matches_service_model(monkeypatch):
    cap = _Capture()
    _patch(monkeypatch, eum_messaging, cap)
    monkeypatch.setenv("EUM_ORIGINATION_IDENTITY", "pool-0123456789abcdef")
    monkeypatch.setenv("SIMULATE_CHANNELS", "false")
    eum_messaging.send_rcs_card("+12065550100", "Estimate?", "Confirm appointment",
                                ["This week", "Next week", "Need parts first"])
    _validate("pinpoint-sms-voice-v2", "SendTextMessage", cap.captured["send_text_message"])


def test_whatsapp_send_text_meta_graph_payload(monkeypatch):
    """WhatsApp now sends via the Meta Cloud (Graph) API over HTTPS, not AWS EUM.
    Validate the exact Graph message payload the adapter posts, without any send."""
    captured = {}

    def fake_post(phone_id, token, payload, timeout=10.0):
        captured["phone_id"] = phone_id
        captured["token"] = token
        captured["payload"] = payload
        return {"messageId": "wamid.TEST", "channel": "whatsapp", "provider": "meta_graph"}

    monkeypatch.setattr(whatsapp, "_graph_post", fake_post)
    monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN", "EAAG-test-token")
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "123456789012345")
    monkeypatch.setenv("SIMULATE_WHATSAPP", "false")

    out = whatsapp.send_text("+12065550100", "Please share a photo of the damage.")

    # Adapter performed a real (mocked) Graph send, not a simulation.
    assert out["provider"] == "meta_graph"
    p = captured["payload"]
    assert p["messaging_product"] == "whatsapp"
    assert p["type"] == "text"
    assert p["to"] == "12065550100"              # leading + stripped for Graph API
    assert p["text"]["body"] == "Please share a photo of the damage."
    assert captured["phone_id"] == "123456789012345"
    assert captured["token"] == "EAAG-test-token"


def test_whatsapp_simulates_without_credentials(monkeypatch):
    """With no token configured, WhatsApp must gracefully simulate (offline demo)."""
    monkeypatch.delenv("WHATSAPP_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("WHATSAPP_PHONE_NUMBER_ID", raising=False)
    monkeypatch.setenv("SIMULATE_WHATSAPP", "false")
    out = whatsapp.send_text("+12065550100", "hello")
    assert out.get("simulated") is True


def test_ses_send_email_matches_service_model(monkeypatch):
    cap = _Capture()
    _patch(monkeypatch, ses_email, cap)
    monkeypatch.setenv("SES_SENDER_EMAIL", "claims@example.com")
    monkeypatch.setenv("SIMULATE_EMAIL", "false")
    ses_email.send_email("lienholder@example.com", "Claim CLM-1 — settlement letter",
                         "Settlement of $4,200.00 approved.")
    _validate("ses", "SendEmail", cap.captured["send_email"])


def test_ses_send_email_with_html_matches_service_model(monkeypatch):
    cap = _Capture()
    _patch(monkeypatch, ses_email, cap)
    monkeypatch.setenv("SES_SENDER_EMAIL", "claims@example.com")
    monkeypatch.setenv("SIMULATE_EMAIL", "false")
    ses_email.send_email("c@example.com", "Summary", "text body",
                         body_html="<b>html body</b>", configuration_set="coe-claims")
    _validate("ses", "SendEmail", cap.captured["send_email"])
