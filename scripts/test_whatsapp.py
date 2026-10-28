#!/usr/bin/env python3
"""Send a single real WhatsApp message via the Meta Graph API to confirm setup.

Usage:
  # loads .env, sends to DEMO_WHATSAPP_TO
  python scripts/test_whatsapp.py
  # or override the recipient / message
  python scripts/test_whatsapp.py +919999999999 "Hello from One Touch Resolve"
  # send the pre-approved hello_world template (needed to OPEN a conversation):
  python scripts/test_whatsapp.py --template +919999999999

Prereqs in .env:
  WHATSAPP_ACCESS_TOKEN, WHATSAPP_PHONE_NUMBER_ID, DEMO_WHATSAPP_TO
  SIMULATE_WHATSAPP=false
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

# Load .env
env = ROOT / ".env"
if env.exists():
    for line in env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

from channels import whatsapp  # noqa: E402


def main() -> int:
    args = [a for a in sys.argv[1:]]
    use_template = "--template" in args
    args = [a for a in args if a != "--template"]

    to = args[0] if args else os.environ.get("DEMO_WHATSAPP_TO", "")
    msg = args[1] if len(args) > 1 else "✅ One Touch Resolve — WhatsApp integration is live."

    if not to:
        print("ERROR: no recipient. Set DEMO_WHATSAPP_TO in .env or pass a number arg.")
        return 2

    token = os.environ.get("WHATSAPP_ACCESS_TOKEN", "")
    pid = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")
    print(f"token set: {bool(token)} | phone_number_id set: {bool(pid)} | to: {to}")
    print(f"will-really-send: {whatsapp._should_send()}  (False => simulated)")

    if use_template:
        res = whatsapp.send_template(to, "hello_world", language="en_US")
        print("template send result:", res)
    else:
        res = whatsapp.send_text(to, msg)
        print("text send result:", res)

    if res.get("provider") == "meta_graph":
        print("\n✅ REAL WhatsApp message sent via Meta Graph API. Check the phone.")
    else:
        print("\nℹ️  Simulated (no token or SIMULATE_WHATSAPP not false). Fill .env to send for real.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
