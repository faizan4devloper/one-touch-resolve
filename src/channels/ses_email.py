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


def send_email(
    to_address: str,
    subject: str,
    body_text: str,
    *,
    body_html: Optional[str] = None,
    sender: Optional[str] = None,
    configuration_set: Optional[str] = None,
) -> dict[str, Any]:
    """Send a transactional email via Amazon SES."""

    from_addr = sender or os.environ.get("SES_SENDER_EMAIL", "")
    if base.simulate_email():
        return {**base.simulated_result("email", to_address, subject=subject), "backend": "ses"}
    if not from_addr:
        raise RuntimeError("SES_SENDER_EMAIL is required for sending email.")
    config_set = configuration_set or os.environ.get("SES_CONFIGURATION_SET")

    body: dict[str, Any] = {"Text": {"Data": body_text, "Charset": "UTF-8"}}
    if body_html:
        body["Html"] = {"Data": body_html, "Charset": "UTF-8"}

    kwargs: dict[str, Any] = {
        "Source": from_addr,
        "Destination": {"ToAddresses": [to_address]},
        "Message": {"Subject": {"Data": subject, "Charset": "UTF-8"}, "Body": body},
    }
    if config_set:
        kwargs["ConfigurationSetName"] = config_set

    resp = _client().send_email(**kwargs)
    return {"messageId": resp.get("MessageId"), "channel": "email", "backend": "ses"}
