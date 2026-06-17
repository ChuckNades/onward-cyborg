from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from typing import Type

from .service import CyborgService


def make_handler(service: CyborgService) -> Type[BaseHTTPRequestHandler]:
    class CyborgHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/api/agenda":
                self._send_json(service.agenda_response())
            elif self.path == "/health":
                self._send_json(service.health_response())
            else:
                self.send_error(404, "not found")

        def log_message(self, format: str, *args: object) -> None:
            return

        def _send_json(self, payload: dict[str, object]) -> None:
            body = json.dumps(payload, sort_keys=True).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return CyborgHandler


def serve(service: CyborgService) -> None:
    server = ThreadingHTTPServer((service.config.host, service.config.port), make_handler(service))
    server.serve_forever()
