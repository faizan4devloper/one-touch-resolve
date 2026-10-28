"""Tests for the external system-of-action tool (open_external_ticket).

Covers the offline/simulated path, the real-HTTP path (urlopen mocked), the
no-id failure case, and that the ticket is recorded on the claim for audit.
"""

import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from shared.models import Claim
from agent.tools import external_action


@pytest.fixture
def store_with_claim(monkeypatch):
    db: dict[str, dict] = {}
    monkeypatch.setattr(external_action.store, "save",
                        lambda c: db.__setitem__(c.claim_id, c.to_item()))
    monkeypatch.setattr(external_action.store, "load",
                        lambda cid: Claim.from_item(db[cid]) if cid in db else None)
    claim = Claim.new("POL-1", "auto_collision")
    db[claim.claim_id] = claim.to_item()
    return claim.claim_id, db


def test_simulated_ticket_when_offline(monkeypatch, store_with_claim):
    cid, db = store_with_claim
    monkeypatch.setenv("SIMULATE_CHANNELS", "true")
    out = external_action.open_external_ticket(cid, "VPN gateway down", system="itsm", priority="P1")
    assert out["simulated"] is True
    assert out["ticket_id"].startswith("SIM-ITSM-")
    # recorded on the claim for audit
    claim = external_action.store.load(cid)
    assert claim.facts["external_tickets"][0]["ticket_id"] == out["ticket_id"]


def test_real_http_post_returns_remote_id(monkeypatch, store_with_claim):
    cid, db = store_with_claim
    monkeypatch.setenv("SIMULATE_CHANNELS", "false")

    captured = {}

    class _Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return json.dumps({"number": "INC0042"}).encode()

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["body"] = json.loads(req.data)
        return _Resp()

    monkeypatch.setattr(external_action.urllib.request, "urlopen", fake_urlopen)
    out = external_action.open_external_ticket(
        cid, "Parts back-ordered", system="servicenow", priority="P2",
        url="https://ops.example.com/intake")
    assert out["simulated"] is False
    assert out["ticket_id"] == "INC0042"
    assert captured["url"] == "https://ops.example.com/intake"
    assert captured["body"]["external_id"] == cid


def test_real_http_no_id_raises(monkeypatch, store_with_claim):
    cid, db = store_with_claim
    monkeypatch.setenv("SIMULATE_CHANNELS", "false")

    class _Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return b"{}"

    monkeypatch.setattr(external_action.urllib.request, "urlopen",
                        lambda req, timeout=None: _Resp())
    with pytest.raises(RuntimeError):
        external_action.open_external_ticket(cid, "x", url="https://ops.example.com/intake")
