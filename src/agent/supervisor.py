"""Supervisor agent — the One Touch Resolve orchestrator.

Runs on Amazon Bedrock AgentCore Runtime using the Strands Agents SDK with
Amazon Nova Pro. The supervisor:

  1. captures FNOL and opens a claim,
  2. fans out to specialist sub-agents (one per external party) on the right channel,
  3. reconciles their commitments at the multi-party commit gate,
  4. re-plans when a party is BLOCKED,
  5. issues settlement once the gate opens.
"""

from __future__ import annotations

import os
from typing import Any, Callable

from agent.tools import claim_tools
from agent.tools import external_action
from agent.tools import fleet_tools
from agent.sub_agents import ALL_SUB_AGENTS, build_subagent_tools

SYSTEM_PROMPT = """You are the One Touch Resolve supervisor for insurance
claims. Your job is to drive a claim from FNOL to settlement by coordinating
multiple independent parties (claimant, repair shop, parts supplier, lienholder),
each on the channel that suits them:
- WhatsApp for the claimant (rich media, two-way)
- RCS (with automatic SMS fallback) for the repair shop
- Email (SES) for lienholder/parts formal notices

Rules:
- Delegate per-party reasoning to the specialist sub-agents. For anything that
  depends on a single party's constraints, call that party's sub-agent tool —
  ask_claimant_agent, ask_repair_shop_agent, ask_parts_supplier_agent, or
  ask_lienholder_agent — passing the task/context as `request`, and use its
  COMMITTED/BLOCKED report to drive your plan. You are the supervisor: you
  reconcile their reports at the commit gate; you do not decide a party's
  position for it.
- Never advance to settlement until the commit gate reports all required parties
  COMMITTED. Call evaluate_commit_gate to check.

- CALL evaluate_commit_gate AT MOST ONCE PER STATE CHANGE. The gate is a pure
  function of party statuses — calling it again WITHOUT having changed a party's
  status in between will always return the identical result. Never poll it in a
  loop. Only call evaluate_commit_gate right after you have taken an action that
  could change a party's status (a commit, a new ETA, a fallback, or a re-plan
  that resolves a block).

- Resolving a BLOCKED party (this is a RE-PLAN, and it MUST change state):
  When evaluate_commit_gate reports a party in `blocked`, that party will stay
  blocked until YOU take a concrete action that changes its status. Pick ONE:
    * parts back-ordered → re-source: call check_parts_eta again with an
      expedited supplier/ETA (<= 2 days) so the parts party becomes COMMITTED,
      OR commit_party on the alternative plan (e.g. approved used/aftermarket
      part), AND arrange a courtesy car for the claimant by calling
      reserve_rental (reserves a REAL vehicle from the managed fleet and messages
      the claimant the details; if it returns reserved:false, open_external_ticket
      and inform the claimant honestly — do not promise a car we don't have).
    * repair shop unavailable → engage_party an alternative shop, then
      commit_party once it confirms.
  Also open_external_ticket so ops has the delay on record, and send_message to
  keep the claimant proactively informed. THEN — and only then — call
  evaluate_commit_gate ONE more time to confirm the block cleared.

- ONE re-plan attempt per blocked party. If after your re-plan the SAME party is
  still blocked, DO NOT evaluate the gate again: open_external_ticket for manual
  handling, send_message to inform the claimant of the delay, and STOP. Report
  that the claim is awaiting the blocked party; do not loop.

- Money never moves without a human. Once the gate is open, call
  request_human_approval to send the adjuster an Approve/Hold card; only after a
  human decision is recorded as 'approved' (record_human_decision) may you call
  issue_settlement. If the decision is 'held' or 'denied', address the concern
  and re-request approval.

- Preserve context across channels. If a channel degrades, continue on SMS with
  the same claim state.
- Be concise. Take actions with tools rather than describing them. Once you have
  reached a terminal state for this turn (claim opened and you were asked to
  stop, gate awaiting a party, approval requested, or settlement issued), STOP
  and report — do not take further tool calls.
"""

# The callable tools the agent may use. Reused by both the live Strands agent and
# the offline planner.
TOOLS: list[Callable[..., Any]] = [
    claim_tools.open_claim,
    claim_tools.record_fact,
    claim_tools.engage_party,
    claim_tools.request_estimate,
    claim_tools.check_parts_eta,
    claim_tools.notify_lienholder,
    claim_tools.commit_party,
    claim_tools.evaluate_commit_gate,
    claim_tools.request_human_approval,
    claim_tools.record_human_decision,
    claim_tools.issue_settlement,
    claim_tools.send_message,
    claim_tools.broadcast_message,
    claim_tools.continue_on_fallback,
    external_action.open_external_ticket,
    # Managed rental fleet — the concrete re-plan when a claimant is without a
    # car (e.g. parts back-ordered): reserve a REAL vehicle, attach it to the
    # claim, and inform the claimant. Honest by design (reserved:false if none).
    fleet_tools.fleet_availability,
    fleet_tools.reserve_rental,
    fleet_tools.return_rental,
]


def build_agent():
    """Construct the live Strands supervisor agent on Bedrock Nova Pro.

    Imported lazily so the package stays usable without the SDK. Sub-agents are
    attached as tools via AgentCore multi-agent collaboration when available.
    """
    from strands import Agent, tool  # type: ignore
    from strands.models import BedrockModel  # type: ignore

    model = BedrockModel(
        model_id=os.environ.get("BEDROCK_MODEL_ID", "amazon.nova-pro-v1:0"),
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
    )

    wrapped = [tool(fn) for fn in TOOLS]
    # Multi-agent collaboration: attach the 4 specialist sub-agents as
    # delegation tools (agents-as-tools). The supervisor calls ask_<party>_agent
    # to have a specialist reason about that party, then reconciles the reports
    # at the commit gate. This makes "1 supervisor + 4 sub-agents" real at
    # runtime, not just a diagram.
    subagent_tools = build_subagent_tools()
    agent = Agent(model=model, system_prompt=SYSTEM_PROMPT,
                  tools=wrapped + subagent_tools)
    return agent


def handle_inbound(event: dict[str, Any]) -> dict[str, Any]:
    """Entry point invoked by the dispatcher for each inbound message.

    ``event`` is the normalized channel event (see ``channels/*.parse_inbound``).
    In live mode this calls the Strands agent; the agent decides which tools to
    invoke. We pass the actor id so AgentCore Memory threads the conversation
    across channels: prior turns (possibly from a different channel) are loaded
    as context, and both the inbound and the agent's reply are persisted.
    """
    from agent import memory

    actor_id = event.get("from", "unknown")
    text = event.get("body", "")
    channel = event.get("channel", "")

    # Load prior cross-channel context for this participant (WhatsApp→SMS etc.).
    prior = memory.context_block(actor_id)
    memory.save_turn(actor_id, "user", f"[{channel}] {text}")

    agent = build_agent()
    prompt = (
        (prior + "\n\n" if prior else "")
        + f"Inbound from {actor_id} via {channel}: {text}\n"
        + f"Context: {event}"
    )
    result = agent(prompt)

    reply = str(result)
    memory.save_turn(actor_id, "assistant", reply)
    return {"actor_id": actor_id, "response": reply}
