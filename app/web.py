"""Tiny stdlib-only HTTP server exposing sync status/history to external
consumers (e.g. a Home Assistant RESTful sensor) without adding a dependency.

Endpoints:
  GET /status - current cycle summary (JSON)
  GET /events - recent download/remove history, newest first (JSON)
"""
import json
import logging
import logging.handlers
import os
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from zoneinfo import ZoneInfo

WEB_PORT = int(os.environ.get('WEB_PORT', '8080'))
HISTORY_FILE = os.environ.get('HISTORY_FILE', '/var/log/lftp-mirror/history.jsonl')
HISTORY_MAX_BYTES = int(os.environ.get('HISTORY_MAX_BYTES', str(5 * 1024 * 1024)))
HISTORY_BACKUP_COUNT = int(os.environ.get('HISTORY_BACKUP_COUNT', '3'))
EVENTS_MAX_LIMIT = 1000

# Event timestamps are rendered in TZ_ID (e.g. "America/New_York") so they
# read naturally in Home Assistant/Grafana; falls back to UTC if TZ_ID is
# unset or not a recognized IANA zone.
try:
    TZ = ZoneInfo(os.environ.get('TZ_ID', 'UTC'))
except Exception as e:
    logging.warning(f"Invalid TZ_ID '{os.environ.get('TZ_ID')}', falling back to UTC: {e}")
    TZ = timezone.utc

_lock = threading.Lock()
_state = {
    "cycle": 0,
    "last_sync_start": None,
    "last_sync_end": None,
    "last_sync_success": None,
    "last_error": None,
    "downloaded": 0,
    "removed": 0,
    "next_sync": None,
    "totals": {"download": 0, "remove": 0},
}

_history_logger = logging.getLogger("lftp_mirror.history")
_history_logger.setLevel(logging.INFO)
_history_logger.propagate = False


def _init_history_logger():
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        HISTORY_FILE, maxBytes=HISTORY_MAX_BYTES, backupCount=HISTORY_BACKUP_COUNT
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    _history_logger.addHandler(handler)


def update_state(**kwargs):
    with _lock:
        _state.update(kwargs)


def get_state():
    with _lock:
        return json.loads(json.dumps(_state))


def record_event(event, path):
    """Append a download/remove event to the history log and bump its total."""
    subfolder = path.split("/", 1)[0] if "/" in path else ""
    entry = {
        "time": datetime.now(TZ).isoformat(timespec="seconds"),
        "event": event,
        "subfolder": subfolder,
        "path": path,
    }
    _history_logger.info(json.dumps(entry))
    with _lock:
        _state["totals"][event] = _state["totals"].get(event, 0) + 1


def _tail_events(limit):
    if not os.path.exists(HISTORY_FILE):
        return []
    with open(HISTORY_FILE, "r") as f:
        lines = f.readlines()[-limit:]
    events = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    events.reverse()
    return events


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        logging.debug("web: " + fmt % args)

    def _send_json(self, payload, status=200):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/status":
            self._send_json(get_state())
        elif parsed.path == "/events":
            qs = parse_qs(parsed.query)
            try:
                limit = int(qs.get("limit", ["50"])[0])
            except ValueError:
                limit = 50
            limit = max(1, min(limit, EVENTS_MAX_LIMIT))
            self._send_json({"events": _tail_events(limit)})
        else:
            self._send_json({"error": "not found"}, status=404)


def start_server():
    """Start the web server on a daemon thread and return it."""
    _init_history_logger()
    server = ThreadingHTTPServer(("0.0.0.0", WEB_PORT), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logging.info(f"🌐 Web server listening on :{WEB_PORT} (/status, /events)")
    return server
