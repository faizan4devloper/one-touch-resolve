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
