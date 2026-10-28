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
from agent.sub_agents import ALL_SUB_AGENTS

SYSTEM_PROMPT = """You are the One Touch Resolve supervisor for insurance
claims. Your job is to drive a claim from FNOL to settlement by coordinating
multiple independent parties (claimant, repair shop, parts supplier, lienholder),
each on the channel that suits them:
- WhatsApp for the claimant (rich media, two-way)
- RCS (with automatic SMS fallback) for the repair shop
- Email (SES) for lienholder/parts formal notices

Rules:
- Never advance to settlement until the commit gate reports all required parties
  COMMITTED. Call evaluate_commit_gate to check.
- Money never moves without a human. Once the gate is open, call
  request_human_approval to send the adjuster an Approve/Hold card; only after a
  human decision is recorded as 'approved' (record_human_decision) may you call
  issue_settlement. If the decision is 'held' or 'denied', address the concern
  and re-request approval.
- If a party is BLOCKED (e.g. parts back-ordered), RE-PLAN: offer an alternative
  (such as a rental), keep the claimant proactively informed, and re-evaluate.
- Preserve context across channels. If a channel degrades, continue on SMS with
  the same claim state.
- When a party is BLOCKED or a delay needs ops tracking, open an external ticket
  (open_external_ticket) so the operations system of record has it.
- Be concise. Take actions with tools rather than describing them.
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
    claim_tools.continue_on_fallback,
    external_action.open_external_ticket,
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
    agent = Agent(model=model, system_prompt=SYSTEM_PROMPT, tools=wrapped)
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
