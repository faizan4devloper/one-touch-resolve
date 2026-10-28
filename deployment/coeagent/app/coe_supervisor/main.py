"""One Touch Resolve — Supervisor on Amazon Bedrock AgentCore Runtime.

The supervisor drives an insurance claim from FNOL to settlement by coordinating
multiple independent parties (claimant, repair shop, parts supplier, lienholder),
each on the channel that suits them, and will not advance to settlement until the
multi-party commit gate reports all required parties COMMITTED.

This entrypoint wraps the COE supervisor's real tool set (ported under coe_agent/
coe_channels/coe_shared) behind the AgentCore @app.entrypoint contract, using the
generated AgentCore Memory session manager for cross-channel continuity.
"""

import os
from typing import Any

from strands import Agent, tool
from bedrock_agentcore.runtime import BedrockAgentCoreApp

from model.load import load_model
from memory.session import get_memory_session_manager

# Real COE coordination tools (plain callables, bundled in the CodeZip).
from coe_agent.tools import claim_tools
from coe_agent.tools import external_action
from coe_agent.sub_agents import ALL_SUB_AGENTS

app = BedrockAgentCoreApp()
log = app.logger

# Phone channels (SMS/RCS/WhatsApp) are not provisioned in this account, so the
# deployed agent runs channel-simulated by default (SES email is the one live
# channel). Override by setting SIMULATE_CHANNELS=false once originators exist.
os.environ.setdefault("SIMULATE_CHANNELS", "true")

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
- If a party is BLOCKED (e.g. parts back-ordered), RE-PLAN: offer an alternative
  (such as a rental), keep the claimant proactively informed, and re-evaluate.
- Preserve context across channels. If a channel degrades, continue on SMS with
  the same claim state.
- When a party is BLOCKED or a delay needs ops tracking, open an external ticket
  (open_external_ticket) so the operations system of record has it.
- Be concise. Take actions with tools rather than describing them.

Sub-agents you coordinate (multi-party = multi-agent): """ + ", ".join(
    f"{s.name} ({s.role.value} on {s.channel.value})" for s in ALL_SUB_AGENTS
) + "."

# The 12 COE coordination tools, wrapped as Strands tools.
_COE_TOOLS = [
    claim_tools.open_claim,
    claim_tools.record_fact,
    claim_tools.engage_party,
    claim_tools.request_estimate,
    claim_tools.check_parts_eta,
    claim_tools.notify_lienholder,
    claim_tools.commit_party,
    claim_tools.evaluate_commit_gate,
    claim_tools.issue_settlement,
    claim_tools.send_message,
    claim_tools.continue_on_fallback,
    external_action.open_external_ticket,
]
tools = [tool(fn) for fn in _COE_TOOLS]


def agent_factory():
    cache: dict[str, Agent] = {}

    def get_or_create_agent(session_id: str, user_id: str) -> Agent:
        key = f"{session_id}/{user_id}"
        if key not in cache:
            cache[key] = Agent(
                model=load_model(),
                session_manager=get_memory_session_manager(session_id, user_id),
                system_prompt=SYSTEM_PROMPT,
                tools=tools,
            )
        return cache[key]

    return get_or_create_agent


get_or_create_agent = agent_factory()


@app.entrypoint
async def invoke(payload: dict[str, Any], context):
    """AgentCore Runtime entrypoint.

    ``payload`` carries at least {"prompt": ...}. The AgentCore session/user ids
    thread cross-channel memory so prior turns (possibly from another channel)
    are loaded as context for this participant.
    """
    log.info("COE supervisor invoked")

    session_id = getattr(context, "session_id", "default-session")
    user_id = getattr(context, "user_id", "default-user")
    agent = get_or_create_agent(session_id, user_id)

    prompt = payload.get("prompt") or payload.get("body") or ""
    stream = agent.stream_async(prompt)

    async for event in stream:
        if "data" in event and isinstance(event["data"], str):
            yield event["data"]


if __name__ == "__main__":
    app.run()
