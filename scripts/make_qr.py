#!/usr/bin/env python3
"""Generate a QR code PNG pointing at the ZCAA simulator URL.

Usage: python3 scripts/make_qr.py "https://<your-cloud9-preview-host>/"
Writes zcaa/web/qr.png and prints the URL.
"""
import sys, qrcode
from pathlib import Path
url = sys.argv[1] if len(sys.argv) > 1 else "http://10.131.87.54:8095/"
img = qrcode.make(url)
out = Path(__file__).resolve().parents[1] / "zcaa" / "web" / "qr.png"
img.save(out)
print("QR ->", out)
print("URL:", url)
