"""ZCAA — Zero Call Accidental Assist.

A customer-experience-first, zero-call post-accident journey. The customer never
calls anyone: the agent reaches out proactively and the customer only taps
Yes / No. Each Yes/No is also the authentication + authorization record for the
action the agent is about to take.

This module is a self-contained conversation state machine that:
  * drives the ZCAA journey step by step,
  * uses REAL Amazon Bedrock to triage damage and decide drivable-vs-tow,
  * sends REAL confirmation emails via Amazon SES at key milestones,
  * returns phone-ready messages for the simulator UI (and, later, WhatsApp/SMS).

No AWS SDK import at module load, so it stays testable offline.
"""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Optional


class Step(str, Enum):
    START = "START"
    SAFETY_CHECK = "SAFETY_CHECK"      # "Are you safe?"
    MEDICAL = "MEDICAL"               # if not safe -> emergency guidance
    DAMAGE_MEDIA = "DAMAGE_MEDIA"     # ask for photos (simulated as a tap)
    TRIAGE = "TRIAGE"                 # AI decides severity + drivable
    TOW_OFFER = "TOW_OFFER"           # if not drivable: offer tow
    TOW_DISPATCH = "TOW_DISPATCH"     # book roadside/tow
    RENTAL_OFFER = "RENTAL_OFFER"     # offer a rental
    REPAIR_OFFER = "REPAIR_OFFER"     # book repair shop
    SUMMARY = "SUMMARY"               # email summary + close
    DONE = "DONE"


class Sender(str, Enum):
    AGENT = "agent"
    CUSTOMER = "customer"
    SYSTEM = "system"     # status chips (tow en route, etc.)


def _now() -> float:
    return time.time()


@dataclass
class Message:
    sender: Sender
    text: str
    # Optional quick-reply buttons the customer can tap. Empty = informational.
    choices: list[str] = field(default_factory=list)
    kind: str = "text"          # text | status | safety | tow | rental | repair | summary
    ts: float = field(default_factory=_now)
    # Stable id so clients can render/dedupe by identity (not list position).
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["sender"] = self.sender.value
        return d


@dataclass
class Session:
    session_id: str
    customer_name: str
    policy_number: str
    location: str
    vehicle: str
    phone: str
    step: Step = Step.START
    messages: list[Message] = field(default_factory=list)
    facts: dict[str, Any] = field(default_factory=dict)
    awaiting: bool = False       # waiting for a customer yes/no?
    created_at: float = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "customer_name": self.customer_name,
            "policy_number": self.policy_number,
            "location": self.location,
            "vehicle": self.vehicle,
            "step": self.step.value,
            "facts": self.facts,
            "awaiting": self.awaiting,
            "messages": [m.to_dict() for m in self.messages],
        }

    @classmethod
    def from_item(cls, item: dict[str, Any]) -> "Session":
        """Rebuild a Session from a persisted DynamoDB item.

        DynamoDB returns numbers as Decimal; normalize them back to float/int so
        downstream arithmetic (e.g. tow ETA) doesn't hit float/Decimal errors.
        """
        from decimal import Decimal

        def _num(v: Any) -> Any:
            if isinstance(v, Decimal):
                return int(v) if v % 1 == 0 else float(v)
            if isinstance(v, dict):
                return {k: _num(x) for k, x in v.items()}
            if isinstance(v, list):
                return [_num(x) for x in v]
            return v

        sess = cls(
            session_id=item["session_id"],
            customer_name=item.get("customer_name", ""),
            policy_number=item.get("policy_number", ""),
            location=item.get("location", ""),
            vehicle=item.get("vehicle", ""),
            phone=item.get("phone", ""),
            step=Step(item.get("step", Step.START.value)),
            facts=_num(dict(item.get("facts", {}))),
            awaiting=bool(item.get("awaiting", False)),
            created_at=float(item.get("created_at", _now())),
        )
        for m in item.get("messages", []):
            sess.messages.append(Message(
                sender=Sender(m.get("sender", "agent")),
                text=m.get("text", ""),
                choices=list(m.get("choices", [])),
                kind=m.get("kind", "text"),
                ts=float(m.get("ts", _now())),
                id=m.get("id", uuid.uuid4().hex[:12]),
            ))
        return sess


# --------------------------------------------------------------------------- #
# Session store: in-memory cache (for fast SSE/lock access) mirrored to
# DynamoDB for durability. The DynamoDB table (coe-claims, key `claim_id`) is
# created by the CDK stack. Behaviour is controlled by COE_STORE_BACKEND:
#   auto     (default) — try DynamoDB, fall back to in-memory on any failure
#   dynamodb           — require DynamoDB (errors propagate)
#   memory             — in-memory only (offline simulator / tests)
# --------------------------------------------------------------------------- #
_SESSIONS: dict[str, Session] = {}

_STORE_BACKEND = os.environ.get("COE_STORE_BACKEND", "auto").lower()
_TABLE_NAME = os.environ.get("ZCAA_TABLE_NAME", os.environ.get("CLAIMS_TABLE_NAME", "coe-claims"))
_ddb_ok: Optional[bool] = None   # cached capability probe
_ddb_table = None


def _table():
    global _ddb_table
    if _ddb_table is None:
        import boto3
        ddb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-1"))
        _ddb_table = ddb.Table(_TABLE_NAME)
    return _ddb_table


def _use_ddb() -> bool:
    global _ddb_ok
    if _STORE_BACKEND == "memory":
        return False
    if _STORE_BACKEND == "dynamodb":
        return True
    if _ddb_ok is None:
        _ddb_ok = True   # optimistic in auto mode; first failure flips it off
    return _ddb_ok


def _ddb_safe(value: Any) -> Any:
    """Recursively convert floats to Decimal (DynamoDB rejects float)."""
    from decimal import Decimal
    if isinstance(value, float):
        # str() avoids binary float precision artifacts in Decimal.
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: _ddb_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_ddb_safe(v) for v in value]
    return value


def _session_item(sess: "Session") -> dict[str, Any]:
    """Serialize a session into a DynamoDB item (key `claim_id`)."""
    return _ddb_safe({
        "claim_id": sess.session_id,     # table partition key
        "session_id": sess.session_id,
        "customer_name": sess.customer_name,
        "policy_number": sess.policy_number,
        "location": sess.location,
        "vehicle": sess.vehicle,
        "phone": sess.phone,
        "step": sess.step.value,
        "facts": sess.facts,
        "awaiting": sess.awaiting,
        "created_at": str(sess.created_at),
        "messages": [m.to_dict() for m in sess.messages],
        "record_type": "zcaa_session",
    })


def _persist(sess: "Session") -> None:
    """Best-effort write of a session to DynamoDB (no-op in memory mode)."""
    global _ddb_ok
    if not _use_ddb():
        return
    try:
        _table().put_item(Item=_session_item(sess))
    except Exception as e:  # noqa: BLE001 — never let persistence break the demo
        if _STORE_BACKEND == "dynamodb":
            raise
        _ddb_ok = False
        print(f"[zcaa.store] DynamoDB persist failed ({e}); using in-memory store")


def load_sessions_from_ddb() -> int:
    """Load any persisted sessions into the in-memory cache at startup.

    Returns the number of sessions restored. Safe no-op if DynamoDB is
    unavailable or disabled.
    """
    global _ddb_ok
    if not _use_ddb():
        return 0
    try:
        resp = _table().scan()
        restored = 0
        with _LOCK:
            for item in resp.get("Items", []):
                if item.get("record_type") and item.get("record_type") != "zcaa_session":
                    continue
                if "session_id" not in item:
                    continue
                sess = Session.from_item(item)
                _SESSIONS[sess.session_id] = sess
                restored += 1
        return restored
    except Exception as e:  # noqa: BLE001
        if _STORE_BACKEND == "dynamodb":
            raise
        _ddb_ok = False
        print(f"[zcaa.store] DynamoDB load failed ({e}); starting with empty store")
        return 0


# The store is read by long-lived SSE threads and written by request-handler
# threads (ThreadingHTTPServer), so all access is guarded by a reentrant lock.
# A Condition on the same lock lets the SSE loop block until something actually
# changes instead of busy-polling.
import threading

_LOCK = threading.RLock()
_CHANGED = threading.Condition(_LOCK)

# Monotonic revision counter, bumped on every state mutation. The SSE endpoint
# waits on _CHANGED and reads this to push updates the instant anything changes.
_REVISION: int = 0


def revision() -> int:
    """Current global mutation revision (increments on any session change)."""
    with _LOCK:
        return _REVISION


def _bump() -> None:
    global _REVISION
    with _CHANGED:
        _REVISION += 1
        _CHANGED.notify_all()


def wait_for_change(last_rev: int, timeout: float) -> int:
    """Block until the revision differs from ``last_rev`` (or ``timeout``).

    Returns the current revision. Used by the SSE loop for event-driven push
    with near-zero idle CPU.
    """
    with _CHANGED:
        if _REVISION == last_rev:
            _CHANGED.wait(timeout=timeout)
        return _REVISION


def get(session_id: str) -> Optional[Session]:
    with _LOCK:
        return _SESSIONS.get(session_id)


def latest() -> Optional[Session]:
    """Most recently created session — the operator view defaults to this."""
    with _LOCK:
        if not _SESSIONS:
            return None
        return max(_SESSIONS.values(), key=lambda s: s.created_at)


def list_sessions() -> list[dict[str, Any]]:
    with _LOCK:
        sessions = sorted(_SESSIONS.values(), key=lambda s: s.created_at, reverse=True)
    out = []
    for s in sessions:
        out.append({"session_id": s.session_id, "customer": s.customer_name,
                    "step": s.step.value, "created_at": s.created_at})
    return out


# Map ZCAA journey steps -> the operator "claim state" pipeline.
_STATE_FOR_STEP = {
    "START": "REPORTED", "SAFETY_CHECK": "REPORTED", "MEDICAL": "REPORTED",
    "DAMAGE_MEDIA": "TRIAGE", "TRIAGE": "TRIAGE",
    "TOW_OFFER": "ASSIST", "TOW_DISPATCH": "ASSIST", "RENTAL_OFFER": "ASSIST",
    "REPAIR_OFFER": "REPAIR", "SUMMARY": "SETTLED", "DONE": "SETTLED",
}
OPERATOR_STATES = ["REPORTED", "TRIAGE", "ASSIST", "REPAIR", "SETTLED"]


def dashboard_view(session_id: str) -> dict[str, Any]:
    """Project a live ZCAA session into the operator (Mission Control) shape.

    This is the SAME claim the customer is tapping through on the phone — the
    operator view is just a second lens on it, not separate data.
    """
    sess = _SESSIONS.get(session_id)
    if sess is None:
        return {"exists": False}
    with _LOCK:
        # Snapshot mutable structures so we don't iterate while a request thread
        # mutates them.
        f = dict(sess.facts)
        messages = list(sess.messages)
        step_val = sess.step.value
        customer_name = sess.customer_name
        vehicle = sess.vehicle
        location = sess.location
        session_id_v = sess.session_id
    triage = f.get("triage", {})

    # Parties, derived from what the journey has arranged so far.
    parties: list[dict[str, Any]] = [{
        "role": "claimant", "name": sess.customer_name, "channel": "whatsapp",
        "status": "safe" if f.get("safety") == "safe" else "engaged",
        "note": sess.vehicle,
    }]
    if f.get("tow"):
        parties.append({"role": "roadside", "name": f["tow"]["provider"], "channel": "sms",
                        "status": "dispatched", "note": f"ETA {f['tow']['eta_min']}m · {f['tow']['ref']}"})
    if f.get("rental"):
        parties.append({"role": "rental", "name": f["rental"]["provider"], "channel": "email",
                        "status": "reserved", "note": f["rental"]["ref"]})
    if f.get("repair"):
        parties.append({"role": "repair_shop", "name": f["repair"]["shop"], "channel": "email",
                        "status": "booked", "note": f"{f['repair']['slot']} · {f['repair']['ref']}"})

    # Timeline from the conversation (agent + system events, customer taps).
    timeline = []
    for m in messages:
        if m.sender == Sender.CUSTOMER:
            timeline.append({"actor": customer_name.split()[0], "kind": "tap",
                             "text": f"Confirmed: {m.text}", "channel": "whatsapp"})
        elif m.sender == Sender.SYSTEM:
            timeline.append({"actor": "System", "kind": m.kind, "text": m.text, "channel": ""})
        else:
            timeline.append({"actor": "ZCAA Agent", "kind": m.kind, "text": m.text, "channel": "whatsapp"})

    channels = {"whatsapp"}
    if f.get("tow"):
        channels.add("sms")
    if f.get("summary_email") or f.get("rental") or f.get("repair"):
        channels.add("email")

    # Multi-party fan-out entry: once the agent has engaged more than just the
    # claimant, surface a single "coordinated update" event that shows WHERE it
    # went — each non-claimant party and the channel it was reached on. This
    # makes the engine's core move (driving several parties at once) visible on
    # the operator timeline rather than implied by the roster alone.
    other_parties = [p for p in parties if p["role"] != "claimant"]
    if len(other_parties) >= 2:
        recipients = [{"role": p["role"], "channel": p["channel"]} for p in other_parties]
        timeline.append({
            "actor": "ZCAA Agent",
            "kind": "fanout",
            "text": f"Coordinated update fanned out to {len(recipients)} parties",
            "channel": "",
            "recipients": recipients,
        })

    tow = tow_status(session_id) if f.get("tow") else {"active": False}

    return {
        "exists": True,
        "session_id": session_id_v,
        "customer": customer_name,
        "vehicle": vehicle,
        "location": location,
        "claim_id": f.get("claim_id", "—"),
        "state": _STATE_FOR_STEP.get(step_val, "REPORTED"),
        "step": step_val,
        "triage": triage,
        "photo": f.get("photo"),
        "parties": parties,
        "timeline": timeline,
        "channels": sorted(channels),
        "consents": len(f.get("consents", [])),
        "tow": tow,
        "settled": step_val == Step.DONE.value,
    }


def _agent(sess: Session, text: str, choices: Optional[list[str]] = None, kind: str = "text") -> None:
    with _LOCK:
        sess.messages.append(Message(Sender.AGENT, text, choices or [], kind))
        sess.awaiting = bool(choices)
    _remember(sess, "assistant", text)
    _send_whatsapp(sess, text, choices)
    _bump()


def _send_whatsapp(sess: Session, text: str, choices: Optional[list[str]] = None) -> None:
    """Send an agent message to the claimant over REAL WhatsApp (Meta Graph API).

    Best-effort: a send failure or missing config never breaks the journey — the
    React phone UI is the mirror; this makes the message actually arrive on the
    customer's WhatsApp. Quick-reply options are appended as a numbered list.
    """
    to = os.environ.get("DEMO_WHATSAPP_TO", "").strip() or (sess.phone or "").strip()
    if not to:
        return
    body = text
    if choices:
        body += "\n\n" + "\n".join(f"{i+1}. {c}" for i, c in enumerate(choices))
    try:
        from channels import whatsapp
        res = whatsapp.send_text(to, body)
        sess.facts.setdefault("whatsapp_sends", []).append(
            {"to": to, "provider": res.get("provider", "sim"), "id": res.get("messageId", "")})
    except Exception as e:  # noqa: BLE001 — never let a send break the demo
        print(f"[zcaa.whatsapp] send failed: {e}")


def _system(sess: Session, text: str, kind: str = "status") -> None:
    with _LOCK:
        sess.messages.append(Message(Sender.SYSTEM, text, [], kind))
    _bump()


def _customer(sess: Session, text: str) -> None:
    with _LOCK:
        sess.messages.append(Message(Sender.CUSTOMER, text, []))
    _remember(sess, "user", text)
    _bump()


def _remember(sess: Session, role: str, text: str) -> None:
    """Persist a turn to AgentCore Memory (best-effort) so the same participant's
    context follows them across channels. Keyed by phone (the cross-channel
    actor id), falling back to the session id offline."""
    try:
        from agent import memory
        memory.save_turn(sess.phone or sess.session_id, role, text,
                         session_id=sess.session_id)
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# Integrations (real when enabled): Bedrock triage + SES email.
# --------------------------------------------------------------------------- #
def _triage(peril: str, description: str) -> dict[str, Any]:
    """Real Bedrock triage. Adds a 'drivable' decision the tow logic depends on."""
    from agent import bedrock
    t = bedrock.triage_fnol(peril, description)
    sev = str(t.get("severity", "moderate")).lower()
    # Severe damage -> not drivable -> tow required.
    t["drivable"] = sev not in ("severe", "major", "total")
    return t


def upload_damage_photo(session_id: str, image_bytes: bytes,
                        content_type: str = "image/jpeg") -> dict[str, Any]:
    """Store the customer's REAL damage photo and run Amazon Bedrock Nova Pro
    VISION on it for a dynamic triage (severity/drivable/reasoning from the
    actual image). Falls back to text triage only if the vision call fails.

    Returns the triage dict. The image is kept as a data URL on the session so
    both the phone and the operator view can render the real photo.
    """
    import base64
    sess = _SESSIONS.get(session_id)
    if sess is None:
        raise KeyError(f"session {session_id} not found")

    b64 = base64.b64encode(image_bytes).decode("ascii")
    data_url = f"data:{content_type};base64,{b64}"

    from agent import bedrock
    try:
        t = bedrock.triage_fnol_vision(
            image_bytes, content_type=content_type,
            peril=sess.facts.get("peril", "auto_collision"),
            note=sess.facts.get("description", ""),
        )
    except Exception as e:  # noqa: BLE001 — vision failure must not block intake
        print(f"[zcaa.vision] vision triage failed ({e}); falling back to text triage")
        t = _triage(sess.facts.get("peril", "auto_collision"),
                    sess.facts.get("description", ""))
        t.setdefault("reasoning", "")
        t["source"] = t.get("source", "bedrock") + "-fallback"

    # Image-validity gate: if the vision model says the photo is NOT a vehicle,
    # reject it honestly — do NOT store it or fabricate a triage. The caller
    # (phone UI) shows the reason and keeps the photo step open for a re-upload.
    if t.get("valid") is False:
        reason = t.get("reject_reason") or "That doesn't look like a photo of your vehicle."
        with _LOCK:
            sess.facts["photo_rejects"] = sess.facts.get("photo_rejects", 0) + 1
        _bump()
        return {"valid": False, "reject_reason": reason, "source": t.get("source", "bedrock-vision")}

    with _LOCK:
        sess.facts["photo"] = data_url
        sess.facts["photo_received"] = True
        sess.facts["triage"] = t
    _persist(sess)
    _bump()
    return t


def _send_email(to_addr: str, subject: str, body: str,
                html: Optional[str] = None) -> dict[str, Any]:
    """Real SES send."""
    from channels import ses_email
    return ses_email.send_email(to_addr, subject, body, body_html=html)


def _tow_eta_minutes(location: str = "", severity: str = "") -> int:
    """Estimate a realistic roadside dispatch ETA via Amazon Bedrock.

    This is a real model call. A live deployment would replace it with the
    roadside provider's dispatch API, which returns the same integer.
    """
    from agent import bedrock
    text = bedrock.converse(
        "You estimate roadside-assistance dispatch ETA in minutes for a "
        "vehicle breakdown. Reply with ONLY an integer number of minutes "
        "(realistic urban range 12-45).",
        f"Location: {location}\nSeverity: {severity or 'unknown'}",
        max_tokens=8, temperature=0,
    )
    digits = "".join(c for c in text if c.isdigit())
    if digits:
        return max(8, min(60, int(digits[:2])))
    return 22


# Progressive tow-tracking stages (simulated telemetry from the roadside provider).
_TOW_STAGES = [
    (0,  "Driver assigned — Ravi K. · white flatbed · KA-01-4477"),
    (6,  "Tow driver en route · 15 min away"),
    (12, "Tow driver 5 min away — please stay near your vehicle"),
    (18, "Tow driver has arrived at your location"),
]


def tow_status(session_id: str) -> dict[str, Any]:
    """Return the current tow-tracking stage based on elapsed time since dispatch.

    The phone polls this after a tow is booked, so the customer sees a live
    'driver approaching' experience without doing anything.
    """
    sess = _SESSIONS.get(session_id)
    if not sess or not sess.facts.get("tow"):
        return {"active": False}
    tow = sess.facts["tow"]
    started = tow.get("dispatched_at", _now())
    # Compress the demo timeline so stages advance every few seconds.
    elapsed_min = (_now() - started) / 1.3
    stage_idx, stage_text = 0, _TOW_STAGES[0][1]
    for i, (mark, text) in enumerate(_TOW_STAGES):
        if elapsed_min >= mark:
            stage_idx, stage_text = i, text
    arrived = stage_idx >= len(_TOW_STAGES) - 1
    remaining = max(0, tow["eta_min"] - int(elapsed_min))
    return {
        "active": True, "arrived": arrived, "stage": stage_idx,
        "text": stage_text, "eta_remaining_min": 0 if arrived else remaining,
        "ref": tow["ref"], "provider": tow["provider"],
    }


# --------------------------------------------------------------------------- #
# Public API: start + respond
# --------------------------------------------------------------------------- #
def start_session(*, customer_name: str, policy_number: str, location: str,
                  vehicle: str, phone: str, peril: str = "auto_collision",
                  description: str = "") -> Session:
    """Begin a ZCAA journey. The agent reaches out first — zero calls from the
    customer. Returns the session with the opening safety-check message."""
    sess = Session(
        session_id=f"ZCAA-{uuid.uuid4().hex[:6].upper()}",
        customer_name=customer_name, policy_number=policy_number,
        location=location, vehicle=vehicle, phone=phone,
    )
    sess.facts["peril"] = peril
    sess.facts["description"] = description or "Vehicle collision detected by telematics."
    with _LOCK:
        _SESSIONS[sess.session_id] = sess

    _loc = (location or "").strip()
    _where = f" near {_loc}" if _loc else ""
    _system(sess, f"Possible collision detected{_where} · {vehicle}", "status")
    _agent(sess,
           f"Hi {customer_name.split()[0]}, this is your insurer's Accident Assist. "
           f"We detected a possible collision. First and most important — are you safe?",
           choices=["Yes, I'm safe", "No, I need help"], kind="safety")
    sess.step = Step.SAFETY_CHECK
    _persist(sess)
    return sess


def respond(session_id: str, answer: str) -> Session:
    """Advance the journey and persist the result to DynamoDB (if enabled)."""
    sess = _respond_impl(session_id, answer)
    _persist(sess)
    return sess


def _respond_impl(session_id: str, answer: str) -> Session:
    """Advance the journey with the customer's tap. `answer` is the button text.
    Each tap is recorded as the authentication/authorization for the next action."""
    sess = _SESSIONS.get(session_id)
    if sess is None:
        raise KeyError(f"session {session_id} not found")
    if not sess.awaiting:
        return sess

    _customer(sess, answer)
    low = answer.strip().lower()
    # "yes"-intent: an affirmative tap, OR a "safe" confirmation that isn't a negation.
    # Parenthesized explicitly so precedence is unambiguous (and testable).
    yes = low.startswith("y") or (("safe" in low) and ("not" not in low))
    sess.awaiting = False
    # Record the authenticated consent for audit.
    sess.facts.setdefault("consents", []).append(
        {"step": sess.step.value, "answer": answer, "ts": _now()})

    step = sess.step

    if step == Step.SAFETY_CHECK:
        if "no" in answer.lower() or "help" in answer.lower():
            _agent(sess,
                   "Your safety comes first. If anyone is injured, please call your local "
                   "emergency number now. I've flagged this as a priority and a specialist "
                   "will stay with you. When you're ready, tap below.",
                   choices=["We're okay now"], kind="safety")
            sess.step = Step.MEDICAL
            sess.facts["safety"] = "assisted"
            return sess
        sess.facts["safety"] = "safe"
        _agent(sess,
               "Glad you're safe. To arrange the right help, could you share a photo of the "
               "damage? Tap below once you've taken it — no typing needed.",
               choices=["Photo sent"], kind="text")
        sess.step = Step.DAMAGE_MEDIA
        return sess

    if step == Step.MEDICAL:
        sess.facts["safety"] = "safe"
        _agent(sess,
               "Thank you. Let's get your car sorted. Could you share a photo of the damage? "
               "Tap below when done.",
               choices=["Photo sent"], kind="text")
        sess.step = Step.DAMAGE_MEDIA
        return sess

    if step == Step.DAMAGE_MEDIA:
        # Prefer the REAL vision triage from the uploaded damage photo (set by
        # upload_damage_photo via Nova Pro vision). Only fall back to text triage
        # if no photo was uploaded (keeps the offline/no-image path working).
        t = sess.facts.get("triage")
        if not t or sess.facts.get("triage", {}).get("source", "").startswith("bedrock") is False:
            t = None
        if not t:
            t = _triage(sess.facts["peril"], sess.facts["description"])
            sess.facts["triage"] = t
        sess.facts["claim_id"] = f"CLM-{uuid.uuid4().hex[:6].upper()}"
        src = t.get("source", "bedrock")
        _system(sess,
                f"AI triage · severity {t['severity']} · est. repair {t.get('est_repair_days','?')}d "
                f"· source {src}", "status")
        # Surface the model's visual reasoning as its own line when present.
        if t.get("reasoning"):
            _system(sess, f"Vision analysis: {t['reasoning']}", "summary")
        if t["drivable"]:
            _agent(sess,
                   f"Thanks. The damage looks {t['severity']} and your car appears drivable. "
                   f"I've opened claim {sess.facts['claim_id']}. Would you like me to book a "
                   f"repair appointment for you?",
                   choices=["Yes, book repair", "Not now"], kind="repair")
            sess.step = Step.REPAIR_OFFER
        else:
            _towloc = (sess.location or "").strip()
            _towphrase = f" to {_towloc}" if _towloc else ""
            _agent(sess,
                   f"Thanks. The damage looks {t['severity']} and your car may not be safe to "
                   f"drive. I've opened claim {sess.facts['claim_id']}. Shall I send a tow truck"
                   f"{_towphrase} right now?",
                   choices=["Yes, send a tow", "No, it's drivable"], kind="tow")
            sess.step = Step.TOW_OFFER
        return sess

    if step == Step.TOW_OFFER:
        if yes:
            eta = _tow_eta_minutes(sess.location, sess.facts.get("triage", {}).get("severity", ""))
            sess.facts["tow"] = {"provider": "AllRoad Roadside", "eta_min": eta,
                                 "ref": f"TOW-{uuid.uuid4().hex[:5].upper()}",
                                 "dispatched_at": _now()}
            _system(sess, f"Roadside dispatched · AllRoad Roadside · ETA {eta} min · "
                          f"ref {sess.facts['tow']['ref']}", "tow")
            _towdest = (sess.location or "").strip() or "your location"
            _agent(sess,
                   f"Done — a tow truck is on its way to {_towdest}, ETA about {eta} minutes. "
                   f"You'll get a text when the driver is close. While you wait, would you like a "
                   f"rental car arranged?",
                   choices=["Yes, arrange rental", "No thanks"], kind="rental")
            sess.step = Step.RENTAL_OFFER
        else:
            _agent(sess,
                   "Understood, no tow. Would you like me to book a repair appointment instead?",
                   choices=["Yes, book repair", "Not now"], kind="repair")
            sess.step = Step.REPAIR_OFFER
        return sess

    if step == Step.RENTAL_OFFER:
        if yes:
            sess.facts["rental"] = {"provider": "Enterprise", "class": "Intermediate",
                                    "ref": f"RNT-{uuid.uuid4().hex[:5].upper()}"}
            _system(sess, f"Rental reserved · Enterprise · ref {sess.facts['rental']['ref']}", "rental")
            _agent(sess, "Your rental is reserved and covered under your policy. "
                         "Shall I also book your repair appointment?",
                   choices=["Yes, book repair", "Not now"], kind="repair")
        else:
            _agent(sess, "No rental — noted. Shall I book your repair appointment?",
                   choices=["Yes, book repair", "Not now"], kind="repair")
        sess.step = Step.REPAIR_OFFER
        return sess

    if step == Step.REPAIR_OFFER:
        if yes:
            sess.facts["repair"] = {"shop": "Bayside Collision", "slot": "Wed 8:30 AM",
                                    "ref": f"RPR-{uuid.uuid4().hex[:5].upper()}"}
            _system(sess, f"Repair booked · Bayside Collision · Wed 8:30 AM · "
                          f"ref {sess.facts['repair']['ref']}", "repair")
            _agent(sess, "Booked — Bayside Collision, Wednesday 8:30 AM. "
                         "I'll email you a full summary now and keep you posted at every step.",
                   choices=["Great, thanks"], kind="text")
        else:
            _agent(sess, "No problem. I'll email you a summary of everything set up so far, "
                         "and you can reply any time to continue.",
                   choices=["Okay"], kind="text")
        sess.step = Step.SUMMARY
        return sess

    if step == Step.SUMMARY:
        _finish(sess)
        sess.step = Step.DONE
        return sess

    return sess


def _summary_html(sess: Session) -> str:
    """A clean, branded HTML summary email."""
    f = sess.facts
    t = f.get("triage", {})
    rows = []

    def row(label, value, ref=""):
        refhtml = (f'<span style="color:#8792a2;font-size:12px"> · {ref}</span>' if ref else "")
        return (f'<tr>'
                f'<td style="padding:10px 14px;border-bottom:1px solid #eef0f4;color:#697386;'
                f'font-size:13px;width:150px">{label}</td>'
                f'<td style="padding:10px 14px;border-bottom:1px solid #eef0f4;color:#1a1f36;'
                f'font-size:13px;font-weight:600">{value}{refhtml}</td></tr>')

    rows.append(row("Claim", f.get("claim_id", "opened")))
    rows.append(row("Vehicle", sess.vehicle or "On file"))
    rows.append(row("Location", sess.location or "Captured at scene"))
    rows.append(row("Safety", "Confirmed safe" if f.get("safety") == "safe" else "Assisted"))
    if t:
        dmg = f"{t.get('severity','?').title()} · est. {t.get('est_repair_days','?')} days"
        rows.append(row("AI damage triage", dmg, f"{t.get('source','?')}"))
        if t.get("reasoning"):
            rows.append(row("Vision assessment", t["reasoning"]))
        rows.append(row("Drivable", "No — tow arranged" if t.get("drivable") is False else "Yes"))
    if f.get("tow"):
        rows.append(row("Tow", f"{f['tow']['provider']} · ETA {f['tow']['eta_min']} min", f['tow']['ref']))
    if f.get("rental"):
        rows.append(row("Rental", f"{f['rental']['provider']} {f['rental']['class']}", f['rental']['ref']))
    if f.get("repair"):
        rows.append(row("Repair", f"{f['repair']['shop']} · {f['repair']['slot']}", f['repair']['ref']))
    rows.append(row("Resolution", "Coordinated end-to-end — zero calls"))

    consents = len(f.get("consents", []))
    return f"""<!doctype html>
<html><body style="margin:0;background:#f6f8fb;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif">
  <div style="max-width:560px;margin:0 auto;padding:24px">
    <div style="background:linear-gradient(135deg,#0f62fe,#0353e9);border-radius:16px 16px 0 0;padding:22px 24px">
      <div style="color:#fff;font-size:18px;font-weight:700;letter-spacing:-.02em">One Touch Resolve — you're covered</div>
      <div style="color:#cfe0ff;font-size:13px;margin-top:4px">Everything below was arranged with zero calls · {consents} taps to authorize</div>
    </div>
    <div style="background:#fff;border:1px solid #e6e9ef;border-top:none;border-radius:0 0 16px 16px;padding:8px 10px 18px">
      <p style="color:#3c4257;font-size:14px;padding:14px 14px 6px;margin:0">Hi {sess.customer_name.split()[0] if sess.customer_name else 'there'}, here's a summary of the assistance we set up right after your incident:</p>
      <table style="width:100%;border-collapse:collapse;margin:6px 0">{''.join(rows)}</table>
      <div style="margin:14px;padding:12px 14px;background:#eaf1ff;border:1px solid #cfe0ff;border-radius:10px;color:#0353e9;font-size:13px">
        You didn't make a single call — the agent coordinated every party for you.
      </div>
      <p style="color:#8792a2;font-size:11px;text-align:center;margin:14px 0 4px">One Touch Resolve · powered by Amazon Bedrock AgentCore &amp; AWS Communication Developer Services (SES, End User Messaging)</p>
    </div>
  </div>
</body></html>"""


def _demo_party_emails() -> dict[str, str]:
    """Resolve the demo party email recipients for the live walkthrough.

    Addresses are read from the environment so REAL inboxes can be shown in the
    demo video while the committed repo stays generic. When unset, they default
    to the generic ``@example.com`` placeholders (what GitHub sees) — so a clone
    never emails a real person, and the filming addresses live only in the
    gitignored ``.env``.

        DEMO_LIENHOLDER_EMAIL   lienholder coverage/settlement notice
        DEMO_PARTS_EMAIL        parts-supplier notice
    """
    return {
        "lienholder": os.environ.get("DEMO_LIENHOLDER_EMAIL", "lienholder@example.com").strip(),
        "parts": os.environ.get("DEMO_PARTS_EMAIL", "parts@example.com").strip(),
    }


def _today_str() -> str:
    import datetime as _dt
    return _dt.datetime.now(_dt.timezone.utc).strftime("%d %b %Y")


def _party_email_html(*, accent: str, eyebrow: str, heading: str, intro: str,
                      rows: list, note: str) -> str:
    """Render an official-looking, branded party notice (inline-styled for email).

    Matches the One Touch Resolve summary email's visual language: a gradient
    header, a clean detail table, a highlighted note, and a service footer — so
    the lienholder/parts notices read like formal insurer communications.
    """
    row_html = "".join(
        f'<tr>'
        f'<td style="padding:10px 16px;border-bottom:1px solid #eef0f4;color:#697386;'
        f'font-size:13px;width:168px">{k}</td>'
        f'<td style="padding:10px 16px;border-bottom:1px solid #eef0f4;color:#1a1f36;'
        f'font-size:13px;font-weight:600">{v}</td></tr>'
        for k, v in rows
    )
    return (
        '<!doctype html><html><body style="margin:0;background:#f6f8fb;'
        'font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif">'
        '<div style="max-width:560px;margin:0 auto;padding:24px">'
        f'<div style="background:linear-gradient(135deg,{accent},{accent}cc);'
        'border-radius:16px 16px 0 0;padding:20px 24px">'
        f'<div style="color:#ffffff;opacity:.85;font-size:11px;font-weight:700;'
        f'letter-spacing:.08em">{eyebrow}</div>'
        f'<div style="color:#fff;font-size:18px;font-weight:700;letter-spacing:-.02em;'
        f'margin-top:3px">{heading}</div>'
        '<div style="color:#ffffffcc;font-size:12px;margin-top:4px">'
        'One Touch Resolve · automated claims coordination</div></div>'
        '<div style="background:#fff;border:1px solid #e6e9ef;border-top:none;'
        'border-radius:0 0 16px 16px;padding:16px 10px 18px">'
        f'<p style="color:#3c4257;font-size:14px;line-height:1.5;padding:4px 16px 8px;'
        f'margin:0">{intro}</p>'
        f'<table style="width:100%;border-collapse:collapse;margin:6px 0">{row_html}</table>'
        f'<div style="margin:14px 16px;padding:12px 14px;background:{accent}14;'
        f'border:1px solid {accent}33;border-radius:10px;color:{accent};font-size:13px">'
        f'{note}</div>'
        '<p style="color:#8792a2;font-size:11px;text-align:center;margin:14px 0 4px">'
        'One Touch Resolve · powered by Amazon Bedrock AgentCore &amp; AWS Communication '
        'Developer Services (SES, End User Messaging)</p>'
        '</div></div></body></html>'
    )


def _send_party_emails(sess: Session) -> None:
    """Send distinct lienholder + parts-supplier notices (multi-party fan-out).

    Only fires when the demo recipients are explicitly configured via
    DEMO_LIENHOLDER_EMAIL / DEMO_PARTS_EMAIL (i.e. during filming). With the
    generic @example.com defaults it is skipped, so a plain clone/CI run never
    attempts a real send to a placeholder address. Recorded on the session so
    the dashboard can show the fan-out to separate party inboxes.
    """
    if sess.facts.get("party_emails"):
        return
    f = sess.facts
    parties = _demo_party_emails()
    # Skip unless real (non-placeholder) addresses were configured for filming.
    configured = {k: v for k, v in parties.items() if v and not v.endswith("@example.com")}
    if not configured:
        return
    claim_id = f.get("claim_id", "claim")
    t = f.get("triage", {}) or {}
    sent: dict[str, Any] = {}

    if "lienholder" in configured:
        rows = [
            ("Claim reference", claim_id),
            ("Policyholder", sess.customer_name or "—"),
            ("Vehicle", sess.vehicle or "—"),
            ("Loss type", (f.get("peril") or "auto_collision").replace("_", " ").title()),
            ("Date of loss", _today_str()),
            ("Coverage status", "Active — claim open"),
            ("Next step", "Settlement letter to follow on adjuster approval"),
        ]
        html = _party_email_html(
            accent="#0f62fe",
            eyebrow="LIENHOLDER COVERAGE NOTICE",
            heading="Coverage confirmation",
            intro=(f"This is a formal notice that an auto claim has been opened on the "
                   f"policy associated with your lien. Coverage is active and the claim "
                   f"is in coordinated processing. No action is required from you at this "
                   f"time; a settlement letter will follow once the adjuster approves."),
            rows=rows,
            note="Formal, auditable notice delivered via Amazon SES.",
        )
        body = (f"Coverage confirmation — claim {claim_id}\n\n"
                f"An auto claim has been opened on the policy associated with your lien. "
                f"Coverage is active; a settlement letter will follow on adjuster approval.\n\n"
                f"Policyholder: {sess.customer_name}\nVehicle: {sess.vehicle}\n"
                f"Claim: {claim_id}\n\n— One Touch Resolve, on behalf of the carrier")
        sent["lienholder"] = {
            "to": configured["lienholder"],
            "result": _send_email(configured["lienholder"],
                                  f"Coverage notice — claim {claim_id}", body, html),
        }

    if "parts" in configured:
        part = (f.get("part") or "OEM replacement component")
        rows = [
            ("Claim reference", claim_id),
            ("Vehicle", sess.vehicle or "—"),
            ("Component required", part),
            ("Damage severity", str(t.get("severity", "—")).title()),
            ("Requested by", _today_str()),
            ("Action needed", "Confirm availability + earliest ETA"),
        ]
        html = _party_email_html(
            accent="#ED7100",
            eyebrow="PARTS SUPPLIER REQUEST",
            heading="Parts availability request",
            intro=(f"We are coordinating repairs for the claim below and need to confirm "
                   f"parts availability. Please reply with current availability and the "
                   f"earliest ETA for the required component so we can schedule the repair."),
            rows=rows,
            note="Time-sensitive — a prompt ETA keeps the repair on schedule.",
        )
        body = (f"Parts availability request — claim {claim_id}\n\n"
                f"Please confirm availability and earliest ETA for: {part}.\n"
                f"Vehicle: {sess.vehicle}\nClaim: {claim_id}\n\n"
                f"— One Touch Resolve, on behalf of the carrier")
        sent["parts"] = {
            "to": configured["parts"],
            "result": _send_email(configured["parts"],
                                  f"Parts request — claim {claim_id}", body, html),
        }

    f["party_emails"] = sent
    names = ", ".join(sent.keys())
    _system(sess, f"Party notices emailed ({names})", "summary")


def _finish(sess: Session) -> None:
    """Send the real SES summary email (HTML + text) and post the closing message."""
    # Idempotent: the summary (and its SES email) is sent exactly once, even if
    # the SUMMARY step is re-entered by repeated taps.
    if sess.facts.get("summary_email"):
        return
    # Multi-party fan-out: distinct lienholder + parts notices when configured
    # for the demo (no-op with the generic @example.com defaults).
    _send_party_emails(sess)
    f = sess.facts
    lines = [
        f"Hi {sess.customer_name},", "",
        "Here's a summary of the assistance arranged after your incident — with zero calls needed:", "",
        f"  Claim: {f.get('claim_id','(opened)')}",
        f"  Vehicle: {sess.vehicle}",
        f"  Location: {sess.location or 'Not provided'}",
        f"  Safety: {f.get('safety','confirmed safe')}",
    ]
    t = f.get("triage", {})
    if t:
        lines.append(f"  Damage: {t.get('severity','?')} (AI: {t.get('source','?')}), "
                     f"est. repair {t.get('est_repair_days','?')} days")
    if f.get("tow"):
        lines.append(f"  Tow: {f['tow']['provider']} · ETA {f['tow']['eta_min']} min · ref {f['tow']['ref']}")
    if f.get("rental"):
        lines.append(f"  Rental: {f['rental']['provider']} {f['rental']['class']} · ref {f['rental']['ref']}")
    if f.get("repair"):
        lines.append(f"  Repair: {f['repair']['shop']} · {f['repair']['slot']} · ref {f['repair']['ref']}")
    lines += ["", "You didn't make a single call — we handled it.", "", "— Accident Assist (ZCAA)"]
    body = "\n".join(lines)

    to_addr = os.environ.get("ZCAA_SUMMARY_EMAIL") or os.environ.get("SES_SENDER_EMAIL", "")
    result = (_send_email(to_addr, f"Your Accident Assist summary — {f.get('claim_id','claim')}",
                          body, _summary_html(sess)) if to_addr else {"skipped": True})
    f["summary_email"] = {"to": to_addr, "result": result}

    sent = "sent" if result.get("messageId") else "prepared"
    _system(sess, f"Summary email {sent}" + (f" to {to_addr}" if to_addr else ""), "summary")
    _agent(sess,
           "All set. Your summary is on its way by email, and I'll message you with tow and repair "
           "updates. Take care — you're covered.", kind="summary")
    sess.awaiting = False
