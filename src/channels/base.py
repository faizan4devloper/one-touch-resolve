"""Channel adapter shared configuration.

The three AWS CDS adapters (EUM SMS/RCS, EUM Social WhatsApp, SES) call the real
AWS APIs via boto3 by default. For offline demos and CI they honor two env flags
so the full journey runs with no live carrier/SES account:

  * SIMULATE_CHANNELS=true  -> SMS/RCS/WhatsApp adapters log the payload instead
                               of sending, and return a synthetic message id.
  * SIMULATE_EMAIL=true     -> the SES adapter does the same for email.

A simulated send returns the same shape a live send would ({"messageId": ...,
"channel": ...}) with ``"simulated": True`` added, so callers and the claim audit
trail are identical in both modes.
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any

log = logging.getLogger("coe.channels")


def aws_region() -> str:
    """The AWS region all channel clients use."""
    return os.environ.get("AWS_REGION", "us-east-1")


def _truthy(value: str) -> bool:
    return value.strip().lower() in ("1", "true", "yes", "on")


def simulate_channels() -> bool:
    """True when SMS/RCS/WhatsApp sends should be simulated (logged, not sent)."""
    return _truthy(os.environ.get("SIMULATE_CHANNELS", "false"))


def simulate_email() -> bool:
    """True when SES email sends should be simulated.

    Defaults to SIMULATE_CHANNELS when SIMULATE_EMAIL is unset, so a single flag
    can turn the whole system offline, while SIMULATE_EMAIL can still be set
    independently (e.g. simulate phones but send real email, as the demo does).
    """
    val = os.environ.get("SIMULATE_EMAIL")
    if val is None:
        return simulate_channels()
    return _truthy(val)


def simulated_result(channel: str, destination: str, **extra: Any) -> dict[str, Any]:
    """Build a synthetic send result and log what WOULD have been sent."""
    mid = f"sim-{uuid.uuid4().hex[:12]}"
    log.info("SIMULATE %s -> %s | %s", channel, destination, extra or "")
    return {"messageId": mid, "channel": channel, "simulated": True, **extra}
