"""Shared domain model for the One Touch Resolve.

This module is intentionally free of AWS SDK imports so it can be unit-tested in
isolation and reused by both the agent (AgentCore Runtime) and the channel
Lambdas. It defines:

* Channel        - the AWS CDS transports the engine can use
* ClaimState     - the lifecycle of a coordinated claim
* PartyRole      - the independent external parties coordinated by the supervisor
* PartyStatus    - per-party commitment status used by the commit gate
* Party / Claim  - the (de)serializable records persisted to DynamoDB

The design principle: **state lives in the record, never in the transport.**
A workflow that starts on RCS can continue on SMS with no lost context because
nothing about the claim depends on the channel it arrived on.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Optional


class Channel(str, Enum):
    """AWS Communication Developer Services transports."""

    WHATSAPP = "whatsapp"   # AWS End User Messaging Social
    RCS = "rcs"             # AWS End User Messaging (rich, interactive)
    SMS = "sms"             # AWS End User Messaging (fallback / time-critical)
    EMAIL = "email"         # Amazon SES (durable, auditable documents)


class ClaimState(str, Enum):
    """Lifecycle of a coordinated claim. Transitions are enforced in ``Claim``."""

    NEW = "NEW"
    FNOL_CAPTURED = "FNOL_CAPTURED"
    PARTIES_ENGAGED = "PARTIES_ENGAGED"
    COMMITTED = "COMMITTED"
    PENDING_APPROVAL = "PENDING_APPROVAL"   # all parties committed; awaiting a human adjuster sign-off
    SETTLED = "SETTLED"


# Allowed forward transitions. The commit gate relies on these being explicit.
#
# Settlement is gated by TWO independent checks: the multi-party commit gate
# (all required parties COMMITTED) AND a human-in-the-loop approval. A claim can
# only reach SETTLED from PENDING_APPROVAL, which it can only reach from
# COMMITTED. This keeps the "no money moves without a human" rule in the state
# machine itself, not just in prompt text.
_ALLOWED_TRANSITIONS: dict[ClaimState, set[ClaimState]] = {
    ClaimState.NEW: {ClaimState.FNOL_CAPTURED},
    ClaimState.FNOL_CAPTURED: {ClaimState.PARTIES_ENGAGED},
    ClaimState.PARTIES_ENGAGED: {ClaimState.COMMITTED, ClaimState.PARTIES_ENGAGED},
    # A held/denied approval sends the claim back to COMMITTED for a re-decision,
    # so COMMITTED <-> PENDING_APPROVAL is intentionally bidirectional.
    ClaimState.COMMITTED: {ClaimState.PENDING_APPROVAL},
    ClaimState.PENDING_APPROVAL: {ClaimState.SETTLED, ClaimState.COMMITTED},
    ClaimState.SETTLED: set(),
}


class PartyRole(str, Enum):
    """The independent external parties the supervisor coordinates."""

    CLAIMANT = "claimant"
    ADJUSTER = "adjuster"
    REPAIR_SHOP = "repair_shop"
    PARTS_SUPPLIER = "parts_supplier"
    LIENHOLDER = "lienholder"
    RENTAL_PROVIDER = "rental_provider"


class PartyStatus(str, Enum):
    """Per-party commitment status. The commit gate advances only when every
    *required* party is ``COMMITTED``."""

    PENDING = "pending"       # not yet engaged
    NOTIFIED = "notified"     # message sent, awaiting reply
    COMMITTED = "committed"   # party has agreed to its part of the plan
    BLOCKED = "blocked"       # party cannot proceed (triggers a re-plan)


def _now() -> int:
    return int(time.time())


@dataclass
class Party:
    """One external party in a claim, owned by a specialist sub-agent."""

    role: PartyRole
    # Contact handle is channel-specific: phone number (E.164) or email address.
    contact: str
    preferred_channel: Channel
    status: PartyStatus = PartyStatus.PENDING
    required_for_commit: bool = True
    last_message: str = ""
    updated_at: int = field(default_factory=_now)

    def to_item(self) -> dict[str, Any]:
        d = asdict(self)
        d["role"] = self.role.value
        d["preferred_channel"] = self.preferred_channel.value
        d["status"] = self.status.value
        return d

    @classmethod
    def from_item(cls, item: dict[str, Any]) -> "Party":
        return cls(
            role=PartyRole(item["role"]),
            contact=item["contact"],
            preferred_channel=Channel(item["preferred_channel"]),
            status=PartyStatus(item.get("status", PartyStatus.PENDING.value)),
            required_for_commit=item.get("required_for_commit", True),
            last_message=item.get("last_message", ""),
            updated_at=item.get("updated_at", _now()),
        )


class InvalidTransition(Exception):
    """Raised when a claim state transition is not allowed."""


@dataclass
class Claim:
    """A coordinated claim. This is the single source of truth persisted to
    DynamoDB and mirrored in AgentCore Memory (keyed by ``actor_id``)."""

    claim_id: str
    policy_number: str
    peril: str                        # e.g. "auto_collision", "water_damage"
    state: ClaimState = ClaimState.NEW
    parties: dict[str, Party] = field(default_factory=dict)
    # Free-form facts the agent accumulates (severity, part ETA, timeline, etc.)
    facts: dict[str, Any] = field(default_factory=dict)
    # Human-in-the-loop approval record. Empty until a human adjuster decides.
    # Shape: {"decision": "approved|held|denied", "approver": str, "note": str,
    #         "decided_at": int, "requested_at": int}
    approval: dict[str, Any] = field(default_factory=dict)
    # Human-readable audit trail of what the engine did and why.
    audit: list[str] = field(default_factory=list)
    created_at: int = field(default_factory=_now)
    updated_at: int = field(default_factory=_now)

    # -- factory -----------------------------------------------------------
    @staticmethod
    def new(policy_number: str, peril: str) -> "Claim":
        return Claim(
            claim_id=f"CLM-{uuid.uuid4().hex[:8].upper()}",
            policy_number=policy_number,
            peril=peril,
        )

    # -- state machine -----------------------------------------------------
    def transition(self, target: ClaimState) -> None:
        allowed = _ALLOWED_TRANSITIONS.get(self.state, set())
        if target not in allowed and target != self.state:
            raise InvalidTransition(f"{self.state.value} -> {target.value} not allowed")
        if target != self.state:
            self.log(f"state {self.state.value} -> {target.value}")
            self.state = target
        self.touch()

    # -- parties -----------------------------------------------------------
    def add_party(self, party: Party) -> None:
        self.parties[party.role.value] = party
        self.touch()

    def set_party_status(self, role: PartyRole, status: PartyStatus, note: str = "") -> None:
        party = self.parties.get(role.value)
        if party is None:
            raise KeyError(f"party {role.value} not on claim {self.claim_id}")
        party.status = status
        party.updated_at = _now()
        if note:
            party.last_message = note
        self.log(f"party {role.value} -> {status.value}" + (f" ({note})" if note else ""))
        self.touch()

    def required_parties(self) -> list[Party]:
        return [p for p in self.parties.values() if p.required_for_commit]

    # -- human-in-the-loop approval ----------------------------------------
    def request_approval(self, approver: str) -> None:
        """Move a COMMITTED claim to PENDING_APPROVAL and record the request.

        No money can move until a human records a decision; this is enforced by
        the state machine (SETTLED is only reachable from PENDING_APPROVAL) and
        by ``is_approved`` below.
        """
        self.approval = {
            "decision": "pending",
            "approver": approver,
            "note": "",
            "requested_at": _now(),
            "decided_at": 0,
        }
        self.transition(ClaimState.PENDING_APPROVAL)
        self.log(f"human approval requested from {approver}")

    def record_decision(self, decision: str, approver: str = "", note: str = "") -> None:
        """Record a human adjuster's decision (approved / held / denied).

        ``approved`` keeps the claim at PENDING_APPROVAL so settlement may
        proceed; ``held``/``denied`` send it back to COMMITTED for a re-decision.
        """
        decision = decision.lower()
        if decision not in ("approved", "held", "denied"):
            raise ValueError(f"invalid approval decision: {decision!r}")
        self.approval.update({
            "decision": decision,
            "approver": approver or self.approval.get("approver", ""),
            "note": note,
            "decided_at": _now(),
        })
        self.log(f"human decision '{decision}' by {self.approval['approver']}"
                 + (f" ({note})" if note else ""))
        if decision != "approved" and self.state == ClaimState.PENDING_APPROVAL:
            # Kick back for re-decision; a fresh approval must be requested again.
            self.transition(ClaimState.COMMITTED)

    def is_approved(self) -> bool:
        """True only when a human explicitly approved this claim for settlement."""
        return self.approval.get("decision") == "approved"

    # -- helpers -----------------------------------------------------------
    def log(self, message: str) -> None:
        self.audit.append(f"[{_now()}] {message}")

    def touch(self) -> None:
        self.updated_at = _now()

    # -- (de)serialization -------------------------------------------------
    def to_item(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "policy_number": self.policy_number,
            "peril": self.peril,
            "state": self.state.value,
            "parties": {k: v.to_item() for k, v in self.parties.items()},
            "facts": self.facts,
            "approval": self.approval,
            "audit": self.audit,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_item(cls, item: dict[str, Any]) -> "Claim":
        return cls(
            claim_id=item["claim_id"],
            policy_number=item["policy_number"],
            peril=item["peril"],
            state=ClaimState(item.get("state", ClaimState.NEW.value)),
            parties={k: Party.from_item(v) for k, v in item.get("parties", {}).items()},
            facts=item.get("facts", {}),
            approval=item.get("approval", {}),
            audit=item.get("audit", []),
            created_at=item.get("created_at", _now()),
            updated_at=item.get("updated_at", _now()),
        )
