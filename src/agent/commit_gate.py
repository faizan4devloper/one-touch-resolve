"""The multi-party commit gate.

This is the headline differentiator of the One Touch Resolve: the claim
does **not** advance to a committing step until *every required party* has
committed. Late or conflicting replies are reconciled, and any party that becomes
``BLOCKED`` forces the supervisor to re-plan rather than advancing.

A single-agent Q&A chatbot cannot reproduce this because there is no notion of
independent parties converging on a shared, gated state.

The gate is deliberately pure (no AWS imports) so it is trivially unit-testable.
"""

from __future__ import annotations

from dataclasses import dataclass

from shared.models import Claim, ClaimState, Party, PartyStatus


@dataclass
class GateDecision:
    """Result of evaluating the commit gate against a claim."""

    can_commit: bool
    blocked: list[str]        # roles that are blocked (need re-plan)
    pending: list[str]        # roles still awaited
    reason: str

    def to_dict(self) -> dict:
        return {
            "can_commit": self.can_commit,
            "blocked": self.blocked,
            "pending": self.pending,
            "reason": self.reason,
        }


def evaluate(claim: Claim) -> GateDecision:
    """Evaluate whether ``claim`` may advance to COMMITTED.

    Rules:
      * Every party with ``required_for_commit`` must be ``COMMITTED``.
      * If any required party is ``BLOCKED``, the gate is closed and names it
        (the supervisor should re-plan around it).
      * Otherwise, any non-committed required party is reported as pending.
    """

    required: list[Party] = claim.required_parties()

    if not required:
        return GateDecision(
            can_commit=False,
            blocked=[],
            pending=[],
            reason="no required parties engaged yet",
        )

    blocked = [p.role.value for p in required if p.status == PartyStatus.BLOCKED]
    pending = [
        p.role.value
        for p in required
        if p.status in (PartyStatus.PENDING, PartyStatus.NOTIFIED)
    ]

    if blocked:
        return GateDecision(
            can_commit=False,
            blocked=blocked,
            pending=pending,
            reason=f"blocked parties require a re-plan: {', '.join(blocked)}",
        )

    if pending:
        return GateDecision(
            can_commit=False,
            blocked=[],
            pending=pending,
            reason=f"awaiting commitment from: {', '.join(pending)}",
        )

    return GateDecision(
        can_commit=True,
        blocked=[],
        pending=[],
        reason="all required parties committed",
    )


def try_commit(claim: Claim) -> GateDecision:
    """Evaluate the gate and, if open, advance the claim NEW→...→COMMITTED.

    Returns the ``GateDecision`` either way. Mutates ``claim`` only when it can
    commit. Advancing to SETTLED is a separate, deliberate step (e.g. after the
    settlement letter is issued) handled by the caller.
    """

    decision = evaluate(claim)
    if decision.can_commit:
        claim.transition(ClaimState.COMMITTED)
        claim.log("commit gate opened: all required parties committed")
    else:
        claim.log(f"commit gate closed: {decision.reason}")
    return decision
