"""Claim persistence with a resilient backend.

Primary backend is DynamoDB (``coe-claims``, partition key ``claim_id``). On the
AgentCore Runtime the conversation itself is persisted in AgentCore Memory, so if
DynamoDB is unavailable (table missing, or the execution role lacks permissions)
we transparently fall back to an in-process store scoped to the runtime instance.

Set ``COE_STORE_BACKEND=memory`` to force the in-process store, or ``=dynamodb``
to require DynamoDB (errors propagate). Default is ``auto`` (try DDB, fall back).
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from shared.models import Claim

log = logging.getLogger(__name__)

_BACKEND = os.environ.get("COE_STORE_BACKEND", "auto").lower()

# In-process fallback store (per runtime instance).
_MEM: dict[str, dict] = {}
_ddb_ok: Optional[bool] = None  # cached capability probe


def _table():
    import boto3

    ddb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    return ddb.Table(os.environ.get("CLAIMS_TABLE_NAME", "coe-claims"))


def _use_ddb() -> bool:
    """Decide whether to use DynamoDB, caching the result.

    In ``auto`` mode we optimistically try DDB and let the first failing call
    flip us to memory. ``dynamodb`` forces DDB; ``memory`` forces fallback.
    """
    global _ddb_ok
    if _BACKEND == "memory":
        return False
    if _BACKEND == "dynamodb":
        return True
    # auto
    if _ddb_ok is None:
        _ddb_ok = True  # try until proven otherwise
    return _ddb_ok


def save(claim: Claim) -> None:
    global _ddb_ok
    if _use_ddb():
        try:
            _table().put_item(Item=claim.to_item())
            return
        except Exception as e:  # noqa: BLE001 - fall back on any DDB failure in auto mode
            if _BACKEND == "dynamodb":
                raise
            log.warning("DynamoDB save failed (%s); falling back to in-process store", e)
            _ddb_ok = False
    _MEM[claim.claim_id] = claim.to_item()


def load(claim_id: str) -> Optional[Claim]:
    global _ddb_ok
    if _use_ddb():
        try:
            resp = _table().get_item(Key={"claim_id": claim_id})
            item = resp.get("Item")
            return Claim.from_item(item) if item else _from_mem(claim_id)
        except Exception as e:  # noqa: BLE001
            if _BACKEND == "dynamodb":
                raise
            log.warning("DynamoDB load failed (%s); falling back to in-process store", e)
            _ddb_ok = False
    return _from_mem(claim_id)


def all_claims() -> list[Claim]:
    """Return all claims (used by the demo dashboard)."""
    if _use_ddb():
        try:
            resp = _table().scan()
            return [Claim.from_item(i) for i in resp.get("Items", [])]
        except Exception:  # noqa: BLE001
            if _BACKEND == "dynamodb":
                raise
    return [Claim.from_item(i) for i in _MEM.values()]


def _from_mem(claim_id: str) -> Optional[Claim]:
    item = _MEM.get(claim_id)
    return Claim.from_item(item) if item else None
