# Agent safety & correctness

The One Touch Resolve keeps the model **out of the decisions that must be
exact**. Three properties are enforced in code — not left to the prompt — and each
is unit-tested.

## 1. A failed write is never reported as done

State-advancing tools (`issue_settlement`, and the commit gate) persist the claim
and then **read it back** before reporting success. The sentence the agent relays
is authored in code from the *verified* record, via
[`agent/safety.py`](../agent/safety.py) `verified_outcome(...)`:

```python
store.save(claim)                       # attempt the write
return safety.verified_outcome(         # confirm it landed, or raise
    claim_id, ClaimState.SETTLED.value, store.load,
    say=f"Claim {claim_id} is settled for ${amount:,.2f}.", amount=amount)
```

If persistence fails or the read-back state disagrees, `OutcomeNotVerified` is
raised and the agent **never** sees a success to relay. Covered by
`tests/test_safety.py::test_issue_settlement_does_not_report_done_if_write_lost`.

## 2. The model cannot change *who* a tool acts on

Identity is taken from the ingress-verified inbound event, not from free text the
model can be talked into changing. `safety.pin_actor(args, trusted_id)` overwrites
any model-supplied actor id with the trusted one before a tool runs, so a crafted
message cannot make the agent act on another participant's record.

## 3. The gate decision is code, not model judgment

Advancing a claim to `COMMITTED` is decided by the pure
[`agent/commit_gate.py`](../agent/commit_gate.py) state machine — every required
party must be `COMMITTED`, and any `BLOCKED` party closes the gate and names
itself for a re-plan. The model can *propose* actions; it cannot *declare* the
gate open. Covered by `tests/test_commit_gate.py`.

## Why it matters

These turn "the agent said it settled the claim" into "the claim record shows
SETTLED, and the sentence the customer received was generated from that verified
record." The model orchestrates; code owns the facts.
