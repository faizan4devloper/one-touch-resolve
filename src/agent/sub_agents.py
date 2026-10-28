"""Specialist sub-agent definitions.

Under AgentCore multi-agent collaboration (GA March 2025), the supervisor
delegates to specialist sub-agents, each owning ONE external party. Modeling
"multi-party" as "multi-agent" is the structural differentiator: each sub-agent
reasons only about its party's constraints and reports a commitment back to the
supervisor, which reconciles them at the commit gate.

Each entry defines the sub-agent's name, the party role it owns, the channel it
prefers, and the system prompt that scopes its reasoning.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from shared.models import Channel, PartyRole


@dataclass(frozen=True)
class SubAgentSpec:
    name: str
    role: PartyRole
    channel: Channel
    system_prompt: str


CLAIMANT_AGENT = SubAgentSpec(
    name="ClaimantAgent",
    role=PartyRole.CLAIMANT,
    channel=Channel.WHATSAPP,
    system_prompt=(
        "You handle the policyholder relationship over WhatsApp. Capture FNOL "
        "details from photos/video, keep the claimant informed with proactive "
        "updates, and never expose other parties' private information. Be brief, "
        "empathetic, and action-oriented."
    ),
)

REPAIR_SHOP_AGENT = SubAgentSpec(
    name="RepairShopAgent",
    role=PartyRole.REPAIR_SHOP,
    channel=Channel.RCS,
    system_prompt=(
        "You coordinate with the repair shop over RCS (with SMS fallback). Request "
        "an estimate and earliest appointment, and report back a COMMITTED or "
        "BLOCKED status. If parts are needed first, flag it so the supervisor can "
        "engage the parts supplier."
    ),
)

PARTS_AGENT = SubAgentSpec(
    name="PartsAgent",
    role=PartyRole.PARTS_SUPPLIER,
    channel=Channel.EMAIL,
    system_prompt=(
        "You confirm parts availability and ETA. If the ETA is short, commit; if "
        "the part is back-ordered, report BLOCKED with the number of days so the "
        "supervisor can offer a rental and re-plan the timeline."
    ),
)

LIENHOLDER_AGENT = SubAgentSpec(
    name="LienholderAgent",
    role=PartyRole.LIENHOLDER,
    channel=Channel.EMAIL,
    system_prompt=(
        "You send the lienholder formal, auditable notices over email (SES): "
        "coverage confirmation and settlement letter. Keep records precise."
    ),
)

ALL_SUB_AGENTS: list[SubAgentSpec] = [
    CLAIMANT_AGENT,
    REPAIR_SHOP_AGENT,
    PARTS_AGENT,
    LIENHOLDER_AGENT,
]


def _tool_name(spec: "SubAgentSpec") -> str:
    """Delegation-tool name the supervisor sees, e.g. ``ask_repair_shop_agent``."""
    return f"ask_{spec.role.value}_agent"


def build_subagent_tools() -> list:
    """Build each specialist sub-agent as a callable *tool* the supervisor can
    delegate to — the agents-as-tools pattern that implements AgentCore
    multi-agent collaboration.

    Each returned callable is a Strands ``@tool``: when the supervisor calls it,
    a dedicated specialist :class:`strands.Agent` (its own scoped system prompt,
    same Bedrock model) reasons about ONLY that party's constraints and returns a
    concise COMMITTED/BLOCKED-style report. The supervisor reconciles those
    reports at the commit gate.

    Imported lazily so the package stays importable without the Strands SDK
    (offline tests and the pure tool layer never touch this).
    """
    from strands import Agent, tool  # type: ignore
    from strands.models import BedrockModel  # type: ignore

    model = BedrockModel(
        model_id=os.environ.get("BEDROCK_MODEL_ID", "amazon.nova-pro-v1:0"),
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
    )

    tools: list = []
    for spec in ALL_SUB_AGENTS:
        # Bind the spec into a factory so each closure captures its own spec.
        def _make(spec: SubAgentSpec):
            specialist = Agent(model=model, system_prompt=spec.system_prompt)

            def _delegate(request: str) -> str:
                """Delegate to this specialist sub-agent and return its report."""
                return str(specialist(request))

            _delegate.__name__ = _tool_name(spec)
            _delegate.__doc__ = (
                f"Delegate to the {spec.name} (owns the {spec.role.value} party, "
                f"prefers {spec.channel.value}). Pass the task/context as "
                f"`request`; returns the specialist's COMMITTED/BLOCKED report. "
                f"Use this to reason about the {spec.role.value}'s constraints "
                f"instead of deciding for them."
            )
            return tool(_delegate)

        tools.append(_make(spec))
    return tools
