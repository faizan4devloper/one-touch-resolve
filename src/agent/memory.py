"""AgentCore Memory — the single cross-channel session store.

The One Touch Resolve's headline promise is *one case state, many
channels*: a workflow that starts on WhatsApp/RCS continues on SMS with full
context because state lives in the record, never in the transport. Amazon Bedrock
AgentCore Memory is where that per-actor conversational state lives (keyed by
``actor_id``), complementing the durable claim record in DynamoDB.

Live-only: requires ``AGENTCORE_MEMORY_ID`` to be set.
"""

from __future__ import annotations

import os
from typing import Any, Optional


def memory_id() -> str:
    """The configured AgentCore Memory resource id."""
    mid = os.environ.get("AGENTCORE_MEMORY_ID", "")
    if not mid:
        raise RuntimeError("AGENTCORE_MEMORY_ID is required for AgentCore Memory.")
    return mid


def _client():
    import boto3

    return boto3.client(
        "bedrock-agentcore", region_name=os.environ.get("AWS_REGION", "us-east-1")
    )


def save_turn(actor_id: str, role: str, content: str,
              *, session_id: Optional[str] = None) -> dict[str, Any]:
    """Append one conversational turn for ``actor_id`` to the session memory.

    ``role`` is typically ``"user"`` or ``"assistant"``. A failed write is
    swallowed (memory is best-effort context, not the system of record — the
    claim record in DynamoDB is).
    """
    if not actor_id:
        return {"stored": False, "reason": "missing actor_id"}

    try:
        _client().create_event(
            memoryId=memory_id(),
            actorId=actor_id,
            sessionId=session_id or actor_id,
            payload=[{"conversational": {"role": role.upper(), "content": {"text": content}}}],
        )
        return {"stored": True, "backend": "agentcore", "actor_id": actor_id}
    except Exception as e:  # pragma: no cover - network/permission dependent
        return {"stored": False, "backend": "agentcore", "error": type(e).__name__}


def recent_turns(actor_id: str, limit: int = 20,
                 *, session_id: Optional[str] = None) -> list[dict[str, Any]]:
    """Return the most recent turns for ``actor_id`` (oldest→newest).

    This is what threads context across channels: on an inbound SMS we can load
    the WhatsApp history that preceded it, because both share the same actor_id.
    """
    if not actor_id:
        return []

    try:
        resp = _client().list_events(
            memoryId=memory_id(),
            actorId=actor_id,
            sessionId=session_id or actor_id,
            maxResults=limit,
        )
        out: list[dict[str, Any]] = []
        for ev in resp.get("events", []):
            for item in ev.get("payload", []):
                conv = item.get("conversational") or {}
                out.append({
                    "role": (conv.get("role") or "").lower(),
                    "content": (conv.get("content") or {}).get("text", ""),
                    "ts": ev.get("eventTimestamp"),
                })
        return out
    except Exception:  # pragma: no cover - network/permission dependent
        return []


def context_block(actor_id: str, limit: int = 12) -> str:
    """Render recent turns as a compact text block to prime the supervisor.

    Empty string when there is no prior context, so it can be concatenated into
    a prompt unconditionally.
    """
    turns = recent_turns(actor_id, limit=limit)
    if not turns:
        return ""
    lines = [f"{t['role']}: {t['content']}" for t in turns if t.get("content")]
    if not lines:
        return ""
    return "Prior cross-channel context for this participant:\n" + "\n".join(lines)
