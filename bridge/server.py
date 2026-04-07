"""
Local HTTP server running on the bridge PC.
The web app calls this directly from the admin's browser (same LAN).
Listens on http://0.0.0.0:7474 by default.
"""

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

from bridge import api, config, device

log = logging.getLogger(__name__)


def _json_response(handler, status: int, data: dict):
    body = json.dumps(data).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    # Allow calls from any origin (the Lovable app domain)
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
    handler.end_headers()
    handler.wfile.write(body)


def _read_body(handler) -> dict:
    length = int(handler.headers.get("Content-Length", 0))
    if length == 0:
        return {}
    raw = handler.rfile.read(length)
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _check_auth(handler) -> bool:
    expected = config.get("local_api_key")
    if not expected:
        return True  # no local key set, open (LAN-only anyway)
    auth = handler.headers.get("Authorization", "")
    return auth == f"Bearer {expected}"


class BridgeHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        log.debug(f"HTTP {fmt % args}")

    def do_OPTIONS(self):
        # CORS preflight
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/health":
            _json_response(self, 200, {"status": "ok", "device_ip": config.get("device_ip")})

        elif path == "/device/ping":
            ok = device.ping()
            _json_response(self, 200, {"reachable": ok})

        elif path == "/device/users":
            if not _check_auth(self):
                _json_response(self, 401, {"error": "unauthorized"})
                return
            try:
                uids = device.get_all_user_ids()
                _json_response(self, 200, {"user_ids": uids})
            except Exception as e:
                _json_response(self, 500, {"error": str(e)})

        else:
            _json_response(self, 404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path

        if not _check_auth(self):
            _json_response(self, 401, {"error": "unauthorized"})
            return

        body = _read_body(self)

        # ── POST /enroll ──────────────────────────────────────────────────────
        # Body: { person_id, person_type, device_user_id, name }
        # Triggers fingerprint enrollment on the device in a background thread
        # so the HTTP response returns immediately while the device waits for finger.
        if path == "/enroll":
            person_id     = body.get("person_id")
            person_type   = body.get("person_type")   # "member" | "staff"
            device_uid    = body.get("device_user_id")
            name          = body.get("name", f"ID {device_uid}")

            if not all([person_id, person_type, device_uid]):
                _json_response(self, 400, {"error": "person_id, person_type and device_user_id are required"})
                return

            # Acknowledge immediately — enrollment blocks until finger is placed
            _json_response(self, 202, {
                "status": "enrolling",
                "message": "Ask the person to place their finger on the reader now.",
                "device_user_id": device_uid,
            })

            # Run enrollment in background thread
            def _do_enroll():
                try:
                    ok = device.enroll_user(user_id=int(device_uid), name=name)
                    if ok:
                        api.confirm_enrollment(
                            person_id=person_id,
                            person_type=person_type,
                            device_user_id=int(device_uid),
                        )
                        log.info(f"Enrollment complete: {person_type} {person_id} → device uid {device_uid}")
                    else:
                        log.warning(f"Enrollment returned no result for device uid {device_uid}")
                except Exception as e:
                    log.error(f"Enrollment error for device uid {device_uid}: {e}")

            threading.Thread(target=_do_enroll, daemon=True).start()

        # ── POST /delete-user ─────────────────────────────────────────────────
        # Body: { device_user_id }
        elif path == "/delete-user":
            device_uid = body.get("device_user_id")
            if not device_uid:
                _json_response(self, 400, {"error": "device_user_id is required"})
                return
            preserve_uid = config.get("wipe_preserve_uid") or 999
            if int(device_uid) == preserve_uid:
                _json_response(self, 403, {"error": f"uid {preserve_uid} is reserved and cannot be deleted"})
                return
            ok = device.delete_user(int(device_uid))
            _json_response(self, 200, {"deleted": ok})

        # ── POST /sync ────────────────────────────────────────────────────────
        # Manually trigger a sync from the web app (e.g. on membership change)
        elif path == "/sync":
            from bridge import sync
            threading.Thread(target=sync.run_nightly, daemon=True).start()
            _json_response(self, 202, {"status": "sync started"})

        else:
            _json_response(self, 404, {"error": "not found"})


def start(host: str = "0.0.0.0", port: int = None):
    port = port or config.get("agent_port") or 7474
    server = HTTPServer((host, port), BridgeHandler)
    log.info(f"Bridge HTTP server listening on {host}:{port}")
    server.serve_forever()


def start_in_thread(port: int = None) -> threading.Thread:
    """Start server in a daemon thread — used by the main run command."""
    t = threading.Thread(target=start, kwargs={"port": port}, daemon=True)
    t.start()
    return t
