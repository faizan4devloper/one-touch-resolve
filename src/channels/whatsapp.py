"""WhatsApp adapter — Meta WhatsApp Cloud API (Graph API) direct.

This project sends WhatsApp via the **Meta Graph API** directly rather than
AWS End User Messaging Social. The EUM-Social WABA onboarding was blocked in
this account, so outbound WhatsApp is sent straight to
``graph.facebook.com/v{ver}/{PHONE_NUMBER_ID}/messages`` with a WABA bearer
token. (Inbound replies are handled by a separate Lambda webhook on the DFS
account; this module covers the outbound/hero path.)

Config (env):
  WHATSAPP_ACCESS_TOKEN     Meta WABA access token (bearer)
  WHATSAPP_PHONE_NUMBER_ID  Meta WABA phone number id (the numeric id)
  WHATSAPP_API_VERSION      Graph API version (default v20.0)

Behaviour:
  * If a token + phone-number-id are configured AND SIMULATE_CHANNELS is not
    forcing simulation -> a real Graph API send is performed.
  * Otherwise -> a simulated result is returned so the offline demo still runs.
  Uses only the standard library (urllib) so no extra dependency is needed.
"""

from __future__ import annotations

import json
import os
import urllib.request
import urllib.error
from typing import Any, Optional

from channels import base
from channels.base import aws_region

_GRAPH_HOST = "https://graph.facebook.com"


def _api_version() -> str:
    return os.environ.get("WHATSAPP_API_VERSION", "v20.0")


def _credentials() -> tuple[str, str]:
    token = os.environ.get("WHATSAPP_ACCESS_TOKEN", "").strip()
    phone_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "").strip()
    return token, phone_id


def _should_send() -> bool:
    """Real send only when creds are present and simulation isn't forced."""
    token, phone_id = _credentials()
    if not token or not phone_id:
        return False
    # SIMULATE_CHANNELS forces simulation for ALL channels; a dedicated
    # SIMULATE_WHATSAPP=false can re-enable real WhatsApp even while other
    # (unprovisioned) channels stay simulated.
    sim_whatsapp = os.environ.get("SIMULATE_WHATSAPP")
    if sim_whatsapp is not None:
        return sim_whatsapp.strip().lower() not in ("1", "true", "yes", "on")
    return not base.simulate_channels()


def _graph_post(phone_id: str, token: str, payload: dict[str, Any],
                timeout: float = 10.0) -> dict[str, Any]:
    url = f"{_GRAPH_HOST}/{_api_version()}/{phone_id}/messages"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (fixed Graph host)
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"WhatsApp Graph API {e.code}: {detail[:300]}") from e
    try:
        out = json.loads(body)
    except json.JSONDecodeError:
        out = {"raw": body[:300]}
    msg_id = ""
    msgs = out.get("messages") or []
    if msgs and isinstance(msgs, list):
        msg_id = msgs[0].get("id", "")
    return {"messageId": msg_id, "channel": "whatsapp", "provider": "meta_graph", "raw": out}


def send_text(destination: str, body: str, *, phone_number_id: Optional[str] = None) -> dict[str, Any]:
    """Send a WhatsApp text message to ``destination`` (E.164, no leading +)."""
    token, phone_id = _credentials()
    phone_id = phone_number_id or phone_id

    if not _should_send():
        return {**base.simulated_result("whatsapp", destination), "body": body}

    # Graph API expects the recipient without a leading "+".
    to = destination.lstrip("+")
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {"preview_url": False, "body": body},
    }
    return _graph_post(phone_id, token, payload)


def send_template(destination: str, template_name: str, *, language: str = "en_US",
                  components: Optional[list[dict[str, Any]]] = None,
                  phone_number_id: Optional[str] = None) -> dict[str, Any]:
    """Send a pre-approved WhatsApp template (required to START a conversation
    outside the 24-hour customer-initiated window)."""
    token, phone_id = _credentials()
    phone_id = phone_number_id or phone_id
    if not _should_send():
        return {**base.simulated_result("whatsapp", destination), "template": template_name}
    payload = {
        "messaging_product": "whatsapp",
        "to": destination.lstrip("+"),
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language},
            **({"components": components} if components else {}),
        },
    }
    return _graph_post(phone_id, token, payload)


def parse_inbound(sns_message: dict[str, Any]) -> dict[str, Any]:
    """Normalize an inbound WhatsApp payload into the engine's event shape.

    Supports both the Meta Cloud API webhook shape (entry/changes/value/messages)
    and a simplified ``{from, message:{text,...}}`` shape used by the sim harness.
    """
    # Meta Cloud API webhook envelope
    try:
        entry = (sns_message.get("entry") or [{}])[0]
        change = (entry.get("changes") or [{}])[0]
        value = change.get("value") or {}
        msgs = value.get("messages") or []
        if msgs:
            m = msgs[0]
            return {
                "channel": "whatsapp",
                "from": m.get("from", ""),
                "body": (m.get("text") or {}).get("body", ""),
                "media_id": (m.get("image") or m.get("video") or {}).get("id"),
                "message_id": m.get("id", ""),
                "s3_media": None,
            }
    except (AttributeError, IndexError, TypeError):
        pass

    # Simplified / simulated shape
    msg = sns_message.get("message", {}) if isinstance(sns_message.get("message"), dict) else {}
    return {
        "channel": "whatsapp",
        "from": sns_message.get("from", ""),
        "body": msg.get("text", sns_message.get("body", "")),
        "media_id": msg.get("media_id") or sns_message.get("mediaId"),
        "message_id": sns_message.get("messageId", msg.get("id", "")),
        "s3_media": msg.get("media_s3"),
    }


def store_media(media_bytes: bytes, key: str, *, content_type: str = "image/jpeg",
                bucket: Optional[str] = None) -> Optional[str]:
    """Persist inbound FNOL media to S3. Returns an s3:// URI or None. Never raises."""
    target = bucket or os.environ.get("INBOUND_MEDIA_BUCKET", "")
    if not target:
        return None
    try:
        import boto3
        boto3.client("s3", region_name=aws_region()).put_object(
            Bucket=target, Key=key, Body=media_bytes, ContentType=content_type
        )
        return f"s3://{target}/{key}"
    except Exception:
        return None


def download_media(media_id: str) -> bytes:
    """Download inbound WhatsApp media bytes via the Meta Graph API (two-step:
    resolve the media URL, then fetch it). Returns b"" on any failure."""
    if not media_id:
        return b""
    token, _ = _credentials()
    if not token:
        return b""
    try:
        # 1) resolve the media id to a temporary URL
        meta_req = urllib.request.Request(
            f"{_GRAPH_HOST}/{_api_version()}/{media_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        with urllib.request.urlopen(meta_req, timeout=10) as r:  # noqa: S310
            info = json.loads(r.read().decode("utf-8"))
        media_url = info.get("url")
        if not media_url:
            return b""
        # 2) fetch the bytes (also requires the bearer token)
        bin_req = urllib.request.Request(media_url, headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(bin_req, timeout=15) as r:  # noqa: S310
            return r.read()
    except Exception:
        return b""
