"""Durable idempotency for inbound message processing.

The dispatcher must not process the same inbound message twice. This module
records seen message ids in the ``coe-dedupe`` DynamoDB table with a TTL
attribute so entries expire automatically.

The conditional write makes ``mark_if_new`` atomic: the first writer for a given
message id wins; concurrent duplicates fail the condition and are reported as
already-seen. This is the correct primitive for at-least-once SNS delivery.
"""

from __future__ import annotations

import os
import time

# How long a processed message id is remembered before its TTL expires.
_DEFAULT_TTL_SECONDS = 24 * 60 * 60  # 24h


def _ttl_seconds() -> int:
    try:
        return int(os.environ.get("DEDUPE_TTL_SECONDS", _DEFAULT_TTL_SECONDS))
    except ValueError:
        return _DEFAULT_TTL_SECONDS


def _table():
    import boto3

    ddb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    return ddb.Table(os.environ.get("DEDUPE_TABLE_NAME", "coe-dedupe"))


def mark_if_new(message_id: str) -> bool:
    """Atomically record ``message_id`` as seen.

    Returns ``True`` if this is the first time we've seen the id (caller should
    process it), or ``False`` if it was already recorded (caller should skip).

    An empty/missing ``message_id`` cannot be de-duplicated; we return ``True`` so
    the message is still processed rather than silently dropped.
    """
    if not message_id:
        return True

    from botocore.exceptions import ClientError

    expires_at = int(time.time()) + _ttl_seconds()
    try:
        _table().put_item(
            Item={"message_id": message_id, "ttl": expires_at},
            ConditionExpression="attribute_not_exists(message_id)",
        )
        return True
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            return False
        # On any other error, prefer processing (at-least-once) over dropping.
        raise
