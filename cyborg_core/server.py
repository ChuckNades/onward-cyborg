from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from typing import Type

from .service import CyborgService

WEB_ROOT = Path(__file__).resolve().parents[1] / "web"

_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".webp": "image/webp",
    ".ico": "image/x-icon",
    ".mp3": "audio/mpeg",
    ".ogg": "audio/ogg",
    ".wav": "audio/wav",
    ".woff2": "font/woff2",
}


def make_handler(service: CyborgService, web_root: Path | None = None) -> Type[BaseHTTPRequestHandler]:
    root = (web_root or WEB_ROOT).resolve()

    class CyborgHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            path = self.path.split("?", 1)[0]
            if path == "/api/agenda":
                self._send_json(service.agenda_response())
            elif path == "/health":
                self._send_json(service.health_response())
            else:
                self._send_static(path)

        def log_message(self, format: str, *args: object) -> None:
            return

        def _send_static(self, path: str) -> None:
            rel = "index.html" if path in ("/", "") else path.lstrip("/")
            target = (root / rel).resolve()
            # Path-traversal guard: target must stay inside the web root.
            if target != root and root not in target.parents:
                self.send_error(404, "not found")
                return
            if not target.is_file():
                self.send_error(404, "not found")
                return
            body = target.read_bytes()
            ctype = _CONTENT_TYPES.get(target.suffix.lower(), "application/octet-stream")
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _send_json(self, payload: dict[str, object]) -> None:
            body = json.dumps(payload, sort_keys=True).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return CyborgHandler


def serve(service: CyborgService, web_root: Path | None = None) -> None:
    server = ThreadingHTTPServer(
        (service.config.host, service.config.port),
        make_handler(service, web_root=web_root),
    )
    server.serve_forever()
