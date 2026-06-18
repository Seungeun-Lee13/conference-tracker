"""
Local dashboard server with edit API.
Usage: python server.py  →  open http://localhost:8765
"""
import json
import os
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import urllib.parse

BASE_DIR   = Path(__file__).parent
JSON_PATH  = BASE_DIR / "conferences.json"
PORT       = 8765


def _load() -> list:
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


def _save(data: list) -> None:
    JSON_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE_DIR), **kwargs)

    def log_message(self, fmt, *args):
        pass  # suppress access log noise

    # ── Route dispatcher ──────────────────────────────────────────────────
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/conferences":
            self._json_response(_load())
        elif parsed.path == "/":
            self.path = "/dashboard/index.html"
            super().do_GET()
        else:
            super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/conferences":
            body = self._read_body()
            records = _load()
            # Upsert by name+year
            for i, r in enumerate(records):
                if r["name"] == body["name"] and r["year"] == body["year"]:
                    records[i] = body
                    _save(records)
                    self._json_response({"ok": True, "action": "updated"})
                    return
            records.append(body)
            _save(records)
            self._json_response({"ok": True, "action": "created"})
        elif parsed.path == "/api/conferences/delete":
            body = self._read_body()
            records = [r for r in _load()
                       if not (r["name"] == body["name"] and r["year"] == body["year"])]
            _save(records)
            self._json_response({"ok": True})
        else:
            self.send_error(404)

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors_headers()
        self.end_headers()

    # ── Helpers ───────────────────────────────────────────────────────────
    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length))

    def _json_response(self, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(200)
        self._cors_headers()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")


if __name__ == "__main__":
    os.chdir(BASE_DIR)
    httpd = HTTPServer(("", PORT), Handler)
    print(f"Conference Tracker running → http://localhost:{PORT}")
    print("Ctrl-C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
