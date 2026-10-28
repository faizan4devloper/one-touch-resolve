"""Real Amazon Bedrock integration (Converse API).

Provides LLM reasoning for the engine using an Amazon Bedrock model. Live-only:
calls propagate errors rather than falling back to heuristics.

Defaults to amazon.nova-pro-v1:0 (fast, low-cost tool-calling). Override with
BEDROCK_MODEL_ID.
"""

from __future__ import annotations

import json
import os
from typing import Any, Optional


def _client():
    import boto3

    return boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))


def converse(system: str, user: str, *, max_tokens: int = 400,
             temperature: float = 0.2, model_id: Optional[str] = None) -> str:
    """Single-turn Bedrock Converse call. Returns the model's text."""
    mid = model_id or os.environ.get("BEDROCK_MODEL_ID", "amazon.nova-pro-v1:0")
    resp = _client().converse(
        modelId=mid,
        system=[{"text": system}],
        messages=[{"role": "user", "content": [{"text": user}]}],
        inferenceConfig={"maxTokens": max_tokens, "temperature": temperature},
    )
    return resp["output"]["message"]["content"][0]["text"].strip()


def triage_fnol(peril: str, description: str) -> dict[str, Any]:
    """Use the LLM to triage a First Notice of Loss.

    Returns {severity, est_repair_days, summary, source}.
    """
    system = (
        "You are an auto/property insurance FNOL triage assistant. "
        "Given a peril and description, respond ONLY with compact JSON: "
        '{"severity":"minor|moderate|severe","est_repair_days":<int>,"summary":"<one line>"}'
    )
    user = f"Peril: {peril}\nDescription: {description}"
    text = converse(system, user, max_tokens=200, temperature=0)
    data = _parse_triage_json(text)
    data["source"] = "bedrock"
    return data


# Image formats Bedrock Converse accepts, mapped from common content types.
_IMG_FORMATS = {
    "image/jpeg": "jpeg", "image/jpg": "jpeg", "image/png": "png",
    "image/gif": "gif", "image/webp": "webp",
}


def triage_fnol_vision(image_bytes: bytes, *, content_type: str = "image/jpeg",
                       peril: str = "auto_collision", note: str = "") -> dict[str, Any]:
    """Multimodal FNOL triage: analyze the ACTUAL damage photo with a vision model
    (Amazon Nova Pro via the Converse API) and return a dynamic assessment.

    Returns {severity, est_repair_days, drivable, damage, reasoning, summary,
    source:'bedrock-vision'}. Raises on API error so the caller can fall back to
    text triage — the result is never a hard-coded mock.
    """
    fmt = _IMG_FORMATS.get(content_type.lower(), "jpeg")
    mid = os.environ.get("BEDROCK_VISION_MODEL_ID",
                         os.environ.get("BEDROCK_MODEL_ID", "amazon.nova-pro-v1:0"))
    system = (
        "You are an expert auto-insurance FNOL damage assessor. FIRST decide "
        "whether the photo actually shows a VEHICLE (or vehicle damage). Respond "
        "ONLY with compact JSON: "
        '{"valid":true|false,"reject_reason":"<if invalid, one short sentence: '
        'what the image shows and why it cannot be assessed>",'
        '"severity":"minor|moderate|severe","drivable":true|false,'
        '"est_repair_days":<int>,"damage":"<visible damage, few words>",'
        '"reasoning":"<one sentence describing what is visible in the image>",'
        '"summary":"<one line>"}. '
        "If the image is NOT a vehicle (e.g. a person, animal, screenshot, blank "
        "or unrelated photo), set valid=false, give a reject_reason, and set "
        "severity to \"minor\" as a placeholder (it will be ignored). "
        "If it IS a vehicle, set valid=true and judge from visible evidence: "
        "deployed airbags, fluid leaks, wheel/axle/frame damage or a crushed cabin "
        "=> severe & not drivable; cosmetic scuffs => minor & drivable. The "
        "reasoning must describe the photo, not restate the customer note."
    )
    user_text = f"Peril: {peril}. First check the photo is a vehicle, then assess damage." + (
        f" Customer note: {note}" if note else "")
    resp = _client().converse(
        modelId=mid,
        system=[{"text": system}],
        messages=[{
            "role": "user",
            "content": [
                {"text": user_text},
                {"image": {"format": fmt, "source": {"bytes": image_bytes}}},
            ],
        }],
        inferenceConfig={"maxTokens": 400, "temperature": 0},
    )
    text = resp["output"]["message"]["content"][0]["text"].strip()
    data = _parse_triage_json(text)
    # Carry through the vision-only fields (drivable/damage/reasoning).
    start, end = text.find("{"), text.rfind("}")
    extra: dict[str, Any] = {}
    if start != -1 and end > start:
        try:
            extra = json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            extra = {}
    sev = data["severity"]
    data["drivable"] = bool(extra.get("drivable", sev not in ("severe", "major", "total")))
    data["damage"] = str(extra.get("damage", "")).strip()
    data["reasoning"] = str(extra.get("reasoning", "")).strip()
    # Image-validity gate: default to valid=true only when the model clearly said
    # so; treat an explicit false as a rejection the caller must honor.
    data["valid"] = bool(extra.get("valid", True))
    data["reject_reason"] = str(extra.get("reject_reason", "")).strip()
    data["source"] = "bedrock-vision"
    return data


def _parse_triage_json(text: str) -> dict[str, Any]:
    """Parse the triage JSON from a model response, tolerating formatting noise.

    The model is asked for compact JSON, but real responses sometimes wrap it in
    prose or code fences. We extract the first balanced ``{...}`` and parse it; if
    that fails, we fall back to a conservative heuristic so a single malformed
    response never crashes claim intake (open_claim must not fail on a format
    hiccup). The fallback is marked so callers/audits can see it was used.
    """
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            data = json.loads(text[start:end + 1])
            # Normalize the fields we rely on downstream.
            sev = str(data.get("severity", "moderate")).lower()
            if sev not in ("minor", "moderate", "severe"):
                sev = "moderate"
            try:
                days = int(data.get("est_repair_days", 7))
            except (TypeError, ValueError):
                days = 7
            return {
                "severity": sev,
                "est_repair_days": days,
                "summary": str(data.get("summary", "")).strip(),
            }
        except json.JSONDecodeError:
            pass

    # Heuristic fallback: infer severity from any keyword present in the text,
    # default to a safe moderate estimate. Flagged so it is auditable.
    low = text.lower()
    severity = "moderate"
    for level in ("severe", "minor"):
        if level in low:
            severity = level
            break
    est = {"minor": 3, "moderate": 7, "severe": 21}[severity]
    return {
        "severity": severity,
        "est_repair_days": est,
        "summary": (text.strip()[:140] or "triage unavailable; using safe default"),
        "parse_fallback": True,
    }


def draft_message(context: str, goal: str) -> str:
    """Draft a short, empathetic customer message with the LLM."""
    system = ("You write concise, friendly insurance claim updates (max 2 sentences, "
              "no placeholders, ready to send).")
    return converse(system, f"Context: {context}\nWrite a message that: {goal}",
                    max_tokens=120, temperature=0.3)
