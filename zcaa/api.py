#!/usr/bin/env python3
"""ZCAA local API + static server (stdlib only — no extra deps).

Serves BOTH React UIs from the Vite build output (``dashboard/dist/``) and a small
JSON API that drives the ZCAA conversation, so you can test the whole zero-call
journey from a phone's browser.

Static routes (served from dashboard/dist/):
  GET  /            -> phone.html   (customer WhatsApp-style app)
  GET  /dashboard   -> index.html   (operator Mission Control)
  GET  /assets/…    -> hashed JS/CSS chunks

JSON API:
  POST /api/start                -> start a session; body: {name,policy,location,vehicle,phone,description}
  POST /api/respond              -> body: {session_id, answer}
  GET  /api/session?id=...       -> current session state
  GET  /api/tow?id=...           -> live tow-tracking stage
  GET  /api/sessions             -> list sessions
  GET  /api/dashboard?id=...     -> operator projection of a session
  GET  /api/stream?id=...        -> Server-Sent Events: push updates on any change

Run:
  ZCAA_SUMMARY_EMAIL=you@verified python3 -m zcaa.api 8090

Then open http://<ec2-public-ip>:8090/ on your phone.
"""

from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

# Make repo root + src/ importable + load .env
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
_envf = ROOT / ".env"
if _envf.exists():
    for line in _envf.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            v = v.split("#", 1)[0].strip().strip('"').strip("'")
            os.environ.setdefault(k.strip(), v)

from zcaa import session as z  # noqa: E402

DASH = ROOT / "ui" / "dist"

_CTYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
    ".map": "application/json; charset=utf-8",
}


def _guess_ctype(name: str) -> str:
    for ext, ct in _CTYPES.items():
        if name.endswith(ext):
            return ct
    return "application/octet-stream"


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj) -> None:
        self._send(code, json.dumps(obj).encode("utf-8"), "application/json; charset=utf-8")

    def _read_json(self) -> dict:
        n = int(self.headers.get("Content-Length", 0) or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except json.JSONDecodeError:
            return {}

    def do_OPTIONS(self):  # CORS preflight
        self._send(204, b"", "text/plain")

    def do_GET(self):
        parsed = urlparse(self.path)
        route = parsed.path
        # ── Single-page React app (Vite build in dist/) ──
        #   /, /demo, /dashboard, /phone  -> index.html (client-side hash router)
        #   /assets/…                     -> hashed JS/CSS chunks
        # Hashed asset requests must return a real 404 when missing (not HTML).
        if route.startswith("/assets/"):
            rel = route.lstrip("/")
            return self._dist(rel, _guess_ctype(rel))
        if route in ("/favicon.svg", "/favicon.ico", "/hcltech-logo.jpg"):
            rel = route.lstrip("/")
            return self._dist(rel, _guess_ctype(rel))
        if route == "/api/session":
            sid = (parse_qs(parsed.query).get("id") or [""])[0]
            sess = z.get(sid)
            if not sess:
                return self._json(404, {"error": "session not found"})
            return self._json(200, sess.to_dict())
        if route == "/api/tow":
            sid = (parse_qs(parsed.query).get("id") or [""])[0]
            return self._json(200, z.tow_status(sid))
        if route == "/api/sessions":
            return self._json(200, {"sessions": z.list_sessions()})
        if route == "/api/dashboard":
            sid = (parse_qs(parsed.query).get("id") or [""])[0]
            if not sid:
                latest = z.latest()
                if latest is None:
                    return self._json(200, {"exists": False})
                sid = latest.session_id
            return self._json(200, z.dashboard_view(sid))
        if route == "/api/stream":
            return self._stream(parse_qs(parsed.query))
        # Unknown /api route -> JSON 404; everything else -> SPA index.html so
        # client-side (hash) routing handles /, /demo, /dashboard, /phone.
        if route.startswith("/api/"):
            return self._json(404, {"error": "not found"})
        return self._dist("index.html", "text/html; charset=utf-8")

    def do_POST(self):
        route = urlparse(self.path).path
        data = self._read_json()
        if route == "/api/start":
            sess = z.start_session(
                customer_name=data.get("name", "Alex Rivera"),
                policy_number=data.get("policy", "HO-000000"),
                location=data.get("location", "Unknown location"),
                vehicle=data.get("vehicle", "Vehicle"),
                phone=data.get("phone", ""),
                description=data.get("description", ""),
            )
            return self._json(200, sess.to_dict())
        if route == "/api/respond":
            try:
                sess = z.respond(data.get("session_id", ""), data.get("answer", ""))
            except KeyError as e:
                return self._json(404, {"error": str(e)})
            return self._json(200, sess.to_dict())
        if route == "/api/upload":
            # Receive the customer's REAL damage photo (base64 data URL or raw
            # base64) and run Amazon Bedrock Nova Pro VISION triage on it.
            import base64 as _b64
            sid = data.get("session_id", "")
            img = data.get("image", "")
            ctype = data.get("content_type", "image/jpeg")
            if "," in img and img.strip().startswith("data:"):
                head, img = img.split(",", 1)
                # data:image/png;base64,...  -> pull the mime out of the header
                if ":" in head and ";" in head:
                    ctype = head.split(":", 1)[1].split(";", 1)[0] or ctype
            try:
                raw = _b64.b64decode(img)
            except Exception:  # noqa: BLE001
                return self._json(400, {"error": "invalid image data"})
            try:
                triage = z.upload_damage_photo(sid, raw, ctype)
            except KeyError as e:
                return self._json(404, {"error": str(e)})
            return self._json(200, {"ok": True, "triage": triage})
        return self._json(404, {"error": "not found"})

    def _stream(self, query: dict):
        """Server-Sent Events: push live updates the instant a session changes.

        Emits two named events:
          * ``dashboard`` — the operator projection (Mission Control)
          * ``session``   — the full session (phone chat + tow)
        A change is detected via the global revision counter; while a tow is
        active we also re-emit on a short tick because tow ETA advances with
        time. This replaces client-side interval polling with true realtime push.
        """
        import time as _t

        sid = (query.get("id") or [""])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("X-Accel-Buffering", "no")  # disable proxy buffering (nginx)
        self.end_headers()

        def resolve_sid() -> str:
            if sid:
                return sid
            latest = z.latest()
            return latest.session_id if latest else ""

        def send_event(name: str, obj) -> bool:
            try:
                payload = json.dumps(obj)
                self.wfile.write(f"event: {name}\ndata: {payload}\n\n".encode("utf-8"))
                self.wfile.flush()
                return True
            except (BrokenPipeError, ConnectionResetError, OSError):
                return False

        last_rev = -1
        last_beat = 0.0
        try:
            while True:
                try:
                    cur = resolve_sid()
                    rev = z.revision()
                    tow_active = False
                    view = None
                    if cur and (rev != last_rev):
                        view = z.dashboard_view(cur)
                        tow_active = bool(
                            view.get("tow", {}).get("active")
                            and not view.get("tow", {}).get("arrived")
                        )
                    elif cur:
                        # No revision change: only rebuild the view if a tow is in
                        # progress (its ETA advances with wall-clock time).
                        t = z.tow_status(cur)
                        tow_active = bool(t.get("active") and not t.get("arrived"))
                        if tow_active:
                            view = z.dashboard_view(cur)

                    if view is not None:
                        if rev != last_rev or tow_active:
                            last_rev = rev
                            if not send_event("dashboard", view):
                                break
                            sess = z.get(cur)
                            if sess and not send_event("session", sess.to_dict()):
                                break
                    elif not cur and rev != last_rev:
                        last_rev = rev
                        if not send_event("dashboard", {"exists": False}):
                            break
                except (BrokenPipeError, ConnectionResetError):
                    break
                except Exception:
                    # Never let a transient error kill the already-open stream
                    # (that would trigger an EventSource reconnect storm). Log
                    # and continue; the next tick re-reads clean state.
                    import traceback

                    traceback.print_exc()

                # Keepalive comment so proxies don't drop the idle stream.
                now = _t.time()
                if now - last_beat > 15:
                    last_beat = now
                    try:
                        self.wfile.write(b": keepalive\n\n")
                        self.wfile.flush()
                    except OSError:
                        break

                # Event-driven wait: block until a mutation bumps the revision,
                # or wake sooner (1s) while a tow is animating; ~15s idle otherwise.
                if tow_active:
                    _t.sleep(1.0)
                else:
                    z.wait_for_change(last_rev, timeout=15.0)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _dist(self, name: str, ctype: str):
        """Serve a file from the Vite build output (dashboard/dist/).

        HTML routes fall back to the requested page if missing; asset requests
        return 404 rather than an HTML fallback so broken chunk URLs are obvious.
        """
        p = DASH / name
        if not p.exists() or p.is_dir():
            if name.endswith(".html"):
                return self._json(
                    404,
                    {"error": "UI not built — run: cd dashboard && npm run build"},
                )
            return self._json(404, {"error": f"asset not found: {name}"})
        return self._send(200, p.read_bytes(), ctype)

    def log_message(self, *_):  # quiet
        pass


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8095
    # Restore any persisted sessions from DynamoDB so state survives restarts.
    try:
        restored = z.load_sessions_from_ddb()
        if restored:
            print(f"ZCAA: restored {restored} session(s) from DynamoDB")
    except Exception as e:  # noqa: BLE001
        print(f"ZCAA: session restore skipped ({e})")
    ThreadingHTTPServer.allow_reuse_address = True
    ThreadingHTTPServer.daemon_threads = True  # don't let SSE loops block Ctrl-C
    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"ZCAA server on http://0.0.0.0:{port}/  (Bedrock + SES live · DynamoDB store)")
    srv.serve_forever()


if __name__ == "__main__":
    main()
