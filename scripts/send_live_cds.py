#!/usr/bin/env python3
"""Live AWS CDS proof — fire real sends through the engine's OWN adapters.

This is the reproducible, at-runtime evidence a judge can re-run after cloning
the repo: it calls the same ``channels/`` adapters the agent uses (not the raw
AWS CLI), so a green run proves the solution exercises AWS Communication
Developer Services live, end to end, through the codebase.

Two AWS CDS services are exercised live:

  1. Amazon SES            -> channels.ses_email.send_email  (real SendEmail)
  2. AWS End User Messaging -> channels.eum_messaging.send_text (real SendTextMessage, SMS)

Both print the AWS-returned MessageId. WhatsApp (Meta Graph) is fired too when a
token is configured; otherwise it is reported as skipped (not a CDS service).

Config is read from .env (see the EUM_* / SES_* keys). Nothing is simulated when
SIMULATE_* flags are false; if a required identifier is missing the script says
exactly what to provision rather than silently simulating.

Usage:
    python3 scripts/send_live_cds.py
    python3 scripts/send_live_cds.py --json
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

# Load .env the same way the ZCAA server does.
_envf = ROOT / ".env"
if _envf.exists():
    for line in _envf.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            v = v.split("#", 1)[0].strip().strip('"').strip("'")
            os.environ.setdefault(k.strip(), v)

from channels import ses_email, eum_messaging, whatsapp  # noqa: E402


def _ok(mid: str) -> bool:
    return bool(mid) and not str(mid).startswith("sim-")


def run() -> dict:
    results: dict[str, dict] = {}

    # 1) Amazon SES (CDS) — live SendEmail via the repo adapter.
    ses_to = os.environ.get("DEMO_LIENHOLDER_EMAIL") or os.environ.get("SES_SENDER_EMAIL", "")
    ses_res = ses_email.send_email(
        ses_to,
        "One Touch Resolve - live SES proof (CDS at runtime)",
        "Claim CLM-DEMO settled for $4,200.00. Sent live via Amazon SES through "
        "the One Touch Resolve channel adapter.",
    )
    results["ses"] = {
        "service": "Amazon SES",
        "cds": True,
        "message_id": ses_res.get("messageId"),
        "live": _ok(ses_res.get("messageId", "")) and not ses_res.get("simulated"),
        "to": ses_to,
    }

    # 2) AWS End User Messaging SMS (CDS) — live SendTextMessage via the adapter.
    sms_to = os.environ.get("EUM_SIMULATOR_SUCCESS_DEST") or os.environ.get("DEMO_REPAIR_SHOP_PHONE", "")
    sms_res = eum_messaging.send_text(
        sms_to,
        "One Touch Resolve: claim CLM-DEMO settled across 4 parties. Live EUM SMS proof.",
        channel_hint="sms",
    )
    results["eum_sms"] = {
        "service": "AWS End User Messaging (SMS)",
        "cds": True,
        "message_id": sms_res.get("messageId"),
        "live": _ok(sms_res.get("messageId", "")) and not sms_res.get("simulated"),
        "to": sms_to,
        "origination_identity": os.environ.get("EUM_ORIGINATION_IDENTITY", ""),
    }

    # 3) WhatsApp (Meta Graph API; not an AWS CDS service) — live only if token set.
    wa_to = os.environ.get("DEMO_WHATSAPP_TO", "")
    if os.environ.get("WHATSAPP_ACCESS_TOKEN") and wa_to:
        wa_res = whatsapp.send_text(wa_to, "One Touch Resolve: live WhatsApp proof.")
        results["whatsapp"] = {
            "service": "WhatsApp (Meta Graph API)",
            "cds": False,
            "message_id": wa_res.get("messageId"),
            "live": _ok(wa_res.get("messageId", "")) and not wa_res.get("simulated"),
            "to": wa_to,
        }
    else:
        results["whatsapp"] = {
            "service": "WhatsApp (Meta Graph API)", "cds": False,
            "skipped": "no WHATSAPP_ACCESS_TOKEN / DEMO_WHATSAPP_TO configured",
        }

    return results


def main() -> int:
    as_json = "--json" in sys.argv
    results = run()

    live_cds = [r for r in results.values() if r.get("cds") and r.get("live")]

    if as_json:
        print(json.dumps({"results": results, "live_cds_count": len(live_cds)}, indent=2))
        return 0 if live_cds else 1

    print("=" * 68)
    print("ONE TOUCH RESOLVE — LIVE AWS CDS PROOF (via repo channel adapters)")
    print("=" * 68)
    for key, r in results.items():
        if r.get("skipped"):
            print(f"  [skip] {r['service']}: {r['skipped']}")
            continue
        state = "LIVE ✅" if r.get("live") else "SIMULATED ⚠"
        tag = "CDS" if r.get("cds") else "non-CDS"
        print(f"  [{state}] {r['service']} ({tag})")
        print(f"          -> {r.get('to','')}  MessageId={r.get('message_id')}")
    print("-" * 68)
    print(f"  AWS CDS services live at runtime: {len(live_cds)} "
          f"({', '.join(r['service'] for r in live_cds)})")
    print("=" * 68)
    return 0 if live_cds else 1


if __name__ == "__main__":
    raise SystemExit(main())
