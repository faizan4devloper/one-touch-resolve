"""Email adapter — Amazon SES.

Used for the formal, on-the-record artifacts in a claim: coverage confirmations,
lienholder notices, and the final settlement letter. Sends live via the Amazon
SES ``SendEmail`` API.

Note: while the AWS account is in the SES sandbox, delivery is limited to
*verified* recipients. Move the account out of the sandbox for general delivery.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from channels import base
from channels.base import aws_region


def _client():
    import boto3

    return boto3.client("ses", region_name=aws_region())


def _as_list(value: Optional[object]) -> list[str]:
    """Normalize a recipient argument to a list of addresses.

    Accepts a single address string (backward compatible), a list/tuple of
    addresses, or ``None`` (→ empty list). Blank entries are dropped.
    """
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    return [str(a).strip() for a in value if str(a).strip()]


def send_email(
    to_address: "str | list[str]",
    subject: str,
    body_text: str,
    *,
    body_html: Optional[str] = None,
    sender: Optional[str] = None,
    configuration_set: Optional[str] = None,
    cc: "Optional[str | list[str]]" = None,
    bcc: "Optional[str | list[str]]" = None,
) -> dict[str, Any]:
    """Send a transactional email via Amazon SES.

    ``to_address`` may be a single address (backward compatible) or a list of
    addresses; ``cc`` / ``bcc`` are optional and accept the same shapes. All
    ``To``/``Cc`` recipients see one another (a shared, auditable notice);
    ``Bcc`` recipients are hidden. Returns the SES ``messageId`` plus the
    recipient count actually addressed.
    """

    to_addrs = _as_list(to_address)
    cc_addrs = _as_list(cc)
    bcc_addrs = _as_list(bcc)
    if not to_addrs and not bcc_addrs:
        raise ValueError("send_email requires at least one To or Bcc recipient")

    from_addr = sender or os.environ.get("SES_SENDER_EMAIL", "")
    if base.simulate_email():
        primary = to_addrs[0] if to_addrs else (bcc_addrs[0] if bcc_addrs else "")
        return {
            **base.simulated_result("email", primary, subject=subject),
            "backend": "ses",
            "recipients": to_addrs,
            "cc": cc_addrs,
            "bcc": bcc_addrs,
            "recipient_count": len(to_addrs) + len(cc_addrs) + len(bcc_addrs),
        }
    if not from_addr:
        raise RuntimeError("SES_SENDER_EMAIL is required for sending email.")
    config_set = configuration_set or os.environ.get("SES_CONFIGURATION_SET")

    body: dict[str, Any] = {"Text": {"Data": body_text, "Charset": "UTF-8"}}
    if body_html:
        body["Html"] = {"Data": body_html, "Charset": "UTF-8"}

    destination: dict[str, Any] = {}
    if to_addrs:
        destination["ToAddresses"] = to_addrs
    if cc_addrs:
        destination["CcAddresses"] = cc_addrs
    if bcc_addrs:
        destination["BccAddresses"] = bcc_addrs

    kwargs: dict[str, Any] = {
        "Source": from_addr,
        "Destination": destination,
        "Message": {"Subject": {"Data": subject, "Charset": "UTF-8"}, "Body": body},
    }
    if config_set:
        kwargs["ConfigurationSetName"] = config_set

    resp = _client().send_email(**kwargs)
    return {
        "messageId": resp.get("MessageId"),
        "channel": "email",
        "backend": "ses",
        "recipients": to_addrs,
        "cc": cc_addrs,
        "bcc": bcc_addrs,
        "recipient_count": len(to_addrs) + len(cc_addrs) + len(bcc_addrs),
    }
