"""Agent-safety / correctness primitives.

Two invariants the One Touch Resolve enforces in CODE, never leaving
them to the model:

1. **A failed write is never reported as done.** State-advancing tools persist
   the claim and then *read it back* to confirm the intended state landed. The
   success sentence returned to the model is authored here from the *verified*
   record — not from the model's own narration. If persistence fails or the
   read-back disagrees, we raise, so the agent cannot report a settlement/commit
   that did not actually happen.

2. **Identity is not model-controlled.** The party/actor a tool acts on is taken
   from the verified inbound event, not from free text the model can be talked
   into changing. ``pin_actor`` overwrites any model-supplied actor id with the
   trusted one before a tool runs.

These are deliberately tiny and pure so they are unit-testable and auditable.
"""

from __future__ import annotations

from typing import Any, Callable


class OutcomeNotVerified(RuntimeError):
    """Raised when a persisted record does not match the intended outcome."""


def verified_outcome(
    claim_id: str,
    expected_state: str,
    reload_fn: Callable[[str], Any],
    say: str,
    **extra: Any,
) -> dict[str, Any]:
    """Return a code-authored outcome ONLY after confirming the write landed.

    ``reload_fn(claim_id)`` must return the freshly persisted claim (or None).
    The claim's ``state`` must equal ``expected_state``; otherwise we raise and
    the agent never sees a success. The returned ``say`` is the exact,
    code-authored sentence the model should relay verbatim.
    """
    persisted = reload_fn(claim_id)
    if persisted is None:
        raise OutcomeNotVerified(f"{claim_id}: record not found after write")
    actual = getattr(persisted, "state", None)
    actual = getattr(actual, "value", actual)
    if actual != expected_state:
        raise OutcomeNotVerified(
            f"{claim_id}: expected state {expected_state!r} but persisted {actual!r}")
    return {"claim_id": claim_id, "state": expected_state, "say": say,
            "verified": True, **extra}


def pin_actor(tool_args: dict, trusted_actor_id: str,
              field: str = "actor_id") -> dict:
    """Force ``field`` in a tool's arguments to the trusted, ingress-verified id.

    The model may choose which tool to call, but it cannot act on another
    participant's record by putting a different id in the arguments.
    """
    if trusted_actor_id:
        tool_args = {**tool_args, field: trusted_actor_id}
    return tool_args
