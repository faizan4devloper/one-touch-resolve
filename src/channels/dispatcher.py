"""Dispatcher Lambda — SNS entry point for all inbound channel events.

Subscribed to the inbound SNS topics for EUM SMS/RCS and EUM Social WhatsApp.
Responsibilities:
  1. Normalize the SNS record into the engine's channel-event shape.
  2. De-duplicate on the inbound message id (idempotency).
  3. Invoke the AgentCore supervisor (or, in simulation, the local handler).

Deployed by the CDK stack in ``infra/``.
"""

from __future__ import annotations

import json
import os
from typing import Any

from channels import eum_messaging, whatsapp
from shared import dedupe


def _normalize(sns_message: dict[str, Any]) -> dict[str, Any]:
    """Route the raw SNS message to the correct channel parser."""
    # EUM SMS/RCS inbound carries originationNumber; WhatsApp carries a message obj.
    if "originationNumber" in sns_message:
        return eum_messaging.parse_inbound(sns_message)
    return whatsapp.parse_inbound(sns_message)


def _persist_media(event: dict[str, Any]) -> dict[str, Any]:
    """If an inbound WhatsApp/RCS message carries media, persist it to S3 and put
    the resulting ``s3://`` reference on the event so the agent can triage from
    the actual FNOL photo/video. Best-effort: never blocks claim intake."""
    if event.get("channel") != "whatsapp":
        return event
    if event.get("s3_media"):
        return event  # already an S3 pointer (e.g. from the sim harness)

    media_id = event.get("media_id")
    if not media_id:
        return event

    # Download the media bytes from the WhatsApp media endpoint and persist to S3.
    media_bytes = whatsapp.download_media(media_id)
    key = f"inbound/{event.get('from', 'unknown')}/{media_id}.jpg"
    ref = whatsapp.store_media(media_bytes, key)
    if ref:
        event["s3_media"] = ref
    return event


def _invoke_agent(event: dict[str, Any]) -> dict[str, Any]:
    # Invoke the AgentCore runtime. Two options are supported:
    #  (a) call the supervisor in-process (if this Lambda ships the agent), or
    #  (b) invoke a separately-deployed AgentCore runtime by ARN.
    runtime_arn = os.environ.get("AGENTCORE_RUNTIME_ARN")
    if runtime_arn:
        import boto3

        client = boto3.client(
            "bedrock-agentcore", region_name=os.environ.get("AWS_REGION", "us-east-1")
        )
        resp = client.invoke_agent_runtime(
            agentRuntimeArn=runtime_arn,
            runtimeSessionId=event.get("from", "session"),
            payload=json.dumps(event).encode("utf-8"),
        )
        body = resp.get("response") or b"{}"
        return {"handled": True, "runtime": json.loads(body)}

    # Fallback: in-process supervisor.
    from agent.supervisor import handle_inbound

    return {"handled": True, **handle_inbound(event)}


def lambda_handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """AWS Lambda entry point. ``event`` is an SNS event envelope."""
    results: list[dict[str, Any]] = []

    for record in event.get("Records", []):
        raw = record.get("Sns", {}).get("Message", "{}")
        try:
            sns_message = json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError:
            sns_message = {"messageBody": raw}

        normalized = _normalize(sns_message)
        normalized = _persist_media(normalized)

        msg_id = normalized.get("message_id") or ""
        if not dedupe.mark_if_new(msg_id):
            results.append({"skipped_duplicate": msg_id})
            continue

        results.append(_invoke_agent(normalized))

    return {"statusCode": 200, "results": results}
