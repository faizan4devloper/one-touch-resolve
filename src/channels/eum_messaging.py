"""AWS End User Messaging adapter — SMS + RCS with automatic RCS→SMS fallback.

Key facts this adapter encodes (verified against the AWS End User Messaging SMS
User Guide, 2026):

* RCS and SMS use the **same** ``SendTextMessage`` API on the ``pinpoint-sms-voice-v2``
  client. Routing is decided by the **origination identity** in the request.
* Sending through a **phone pool** (recommended) that contains both an **AWS RCS
  Agent** and a **dedicated SMS number/sender ID** gives **automatic RCS→SMS
  fallback**: RCS is attempted first, SMS is used if the device/carrier can't do RCS.
* **Shared routes are NOT supported** for RCS fallback — the pool/account must
  contain a dedicated originator valid for the destination country, or the send
  fails. This is why we always send via ``EUM_ORIGINATION_IDENTITY`` (the pool).

Because the engine keeps all state in the claim record (not in the transport),
"channel-aware continuity" is a natural consequence: a conversation that starts
on RCS continues on SMS with no lost context.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from channels import base
from channels.base import aws_region

_API = "pinpoint-sms-voice-v2"


def _client():
    import boto3

    return boto3.client(_API, region_name=aws_region())


def send_text(
    destination: str,
    body: str,
    *,
    message_type: str = "TRANSACTIONAL",
    origination_identity: Optional[str] = None,
    channel_hint: str = "rcs",
) -> dict[str, Any]:
    """Send an RCS-or-SMS text via pool-based sending (automatic fallback).

    Parameters
    ----------
    destination: recipient phone number in E.164 (e.g. ``+15555550100``).
    body: message text.
    message_type: ``TRANSACTIONAL`` (default) or ``PROMOTIONAL``.
    origination_identity: the phone-pool ARN/ID. Defaults to
        ``EUM_ORIGINATION_IDENTITY`` from the environment. Sending via the pool
        is what enables RCS→SMS fallback.
    channel_hint: retained for call-site compatibility; the live pool call
        handles RCS-first with automatic SMS fallback regardless of its value.
    """

    origin = origination_identity or os.environ.get("EUM_ORIGINATION_IDENTITY", "")
    if base.simulate_channels():
        return {**base.simulated_result("rcs_or_sms", destination), "body": body}
    if not origin:
        raise RuntimeError(
            "EUM_ORIGINATION_IDENTITY is required for sending. A phone pool "
            "with an RCS Agent + dedicated SMS originator enables RCS→SMS fallback."
        )

    resp = _client().send_text_message(
        DestinationPhoneNumber=destination,
        OriginationIdentity=origin,
        MessageBody=body,
        MessageType=message_type,
    )
    return {"messageId": resp.get("MessageId"), "channel": "rcs_or_sms"}


def send_rcs_card(
    destination: str,
    title: str,
    description: str,
    options: list[str],
    *,
    origination_identity: Optional[str] = None,
) -> dict[str, Any]:
    """Send an RCS rich card rendered as a text message with a numbered option
    list. The pool-based text send carries automatic SMS fallback.
    """

    numbered = "\n".join(f"{i+1}. {opt}" for i, opt in enumerate(options))
    body = f"{title}\n{description}\n{numbered}"
    return send_text(destination, body, origination_identity=origination_identity)


def parse_inbound(sns_message: dict[str, Any]) -> dict[str, Any]:
    """Normalize an inbound EUM SMS/RCS SNS payload into the engine's event shape.

    The inbound payload format is shared by SMS and RCS (per AWS docs):
    ``originationNumber``, ``destinationNumber``, ``messageBody``,
    ``messageKeyword``, ``inboundMessageId``, ``previousPublishedMessageId``.
    """

    return {
        "channel": "sms_rcs",
        "from": sns_message.get("originationNumber", ""),
        "to": sns_message.get("destinationNumber", ""),
        "body": sns_message.get("messageBody", ""),
        "keyword": sns_message.get("messageKeyword", ""),
        "message_id": sns_message.get("inboundMessageId", ""),
        "in_reply_to": sns_message.get("previousPublishedMessageId", ""),
    }
