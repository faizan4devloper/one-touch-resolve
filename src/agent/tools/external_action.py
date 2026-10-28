"""External system-of-action: open a ticket in an ITSM / ops system.

The engine doesn't only message people — it can take an action in an external
system of record. This tool posts a ticket to an HTTP endpoint (e.g. a
ServiceNow Table API inbound, a Jira webhook, or any ops intake). It is written
with the standard library only (no extra deps) and is **simulate-aware**:

  * SIMULATE_CHANNELS=true (or no COE_TICKET_WEBHOOK_URL set) -> it logs and
    returns a synthetic ticket id, so the full journey runs offline.
  * otherwise -> it performs a real HTTPS POST and returns the remote response.

Kept behind the same plain-callable tool pattern as the other claim tools so the
Strands supervisor can register it directly and tests can call it without AWS.
"""

from __future__ import annotations

import json
import os
import urllib.request
import uuid
from typing import Any, Optional

from shared import store
from channels import base


def open_external_ticket(
    claim_id: str,
    summary: str,
    *,
    system: str = "itsm",
    priority: str = "P3",
    url: Optional[str] = None,
    timeout: float = 5.0,
) -> dict[str, Any]:
    """Open a ticket for ``claim_id`` in an external ops/ITSM system.

    Returns {ticket_id, system, status, simulated?}. The claim audit records the
    ticket id so the outcome is traceable. A live POST failure raises (the agent
    must not report a ticket it did not create) — mirroring the "failed write is
    never reported as done" invariant.
    """
    endpoint = url or os.environ.get("COE_TICKET_WEBHOOK_URL", "")
    payload = {
        "external_id": claim_id,
        "summary": summary,
        "priority": priority,
        "source": "coordinated-outcome-engine",
    }

    # Offline / unconfigured -> deterministic simulated ticket.
    if base.simulate_channels() or not endpoint:
        ticket_id = f"SIM-{system.upper()}-{uuid.uuid4().hex[:8].upper()}"
        base.simulated_result(f"ticket:{system}", endpoint or "(no endpoint)", summary=summary)
        result = {"ticket_id": ticket_id, "system": system, "status": "created",
                  "simulated": True}
    else:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(endpoint, data=data, method="POST",
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (configured endpoint)
            body = resp.read().decode("utf-8", errors="replace")
        try:
            remote = json.loads(body)
        except json.JSONDecodeError:
            remote = {"raw": body[:500]}
        ticket_id = str(remote.get("ticket_id") or remote.get("number") or remote.get("id") or "")
        if not ticket_id:
            raise RuntimeError(f"external ticket system returned no id: {body[:200]}")
        result = {"ticket_id": ticket_id, "system": system, "status": "created",
                  "simulated": False}

    # Record on the claim so the ticket is auditable alongside the outcome.
    claim = store.load(claim_id)
    if claim is not None:
        claim.facts.setdefault("external_tickets", []).append(
            {"system": system, "ticket_id": result["ticket_id"], "priority": priority})
        claim.log(f"external {system} ticket {result['ticket_id']} opened: {summary}")
        store.save(claim)
    return {"claim_id": claim_id, **result}
