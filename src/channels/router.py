"""Channel router — the single ``send_message`` entry point for the engine.

The agent's tools never call a specific carrier API directly; they call
``route_message`` with a :class:`~shared.models.Channel`. This keeps the agent
channel-agnostic and makes "channel-aware continuity" a routing concern rather
than an agent concern.
"""

from __future__ import annotations

from typing import Any, Optional

from shared.models import Channel
from channels import eum_messaging, ses_email, whatsapp


def route_message(
    channel: Channel,
    destination: str,
    body: str,
    *,
    subject: Optional[str] = None,
    rcs_options: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Send ``body`` to ``destination`` over ``channel``.

    * WHATSAPP -> EUM Social text
    * RCS      -> EUM rich card (with automatic SMS fallback via the pool)
    * SMS      -> EUM text (pool-based; also carries fallback)
    * EMAIL    -> Amazon SES (``subject`` required)
    """

    if channel == Channel.WHATSAPP:
        return whatsapp.send_text(destination, body)

    if channel == Channel.RCS:
        if rcs_options:
            return eum_messaging.send_rcs_card(
                destination, subject or "Please choose", body, rcs_options
            )
        return eum_messaging.send_text(destination, body, channel_hint="rcs")

    if channel == Channel.SMS:
        return eum_messaging.send_text(destination, body, channel_hint="sms")

    if channel == Channel.EMAIL:
        return ses_email.send_email(destination, subject or "Your claim update", body)

    raise ValueError(f"unsupported channel: {channel}")
