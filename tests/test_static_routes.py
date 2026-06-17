from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import threading
from urllib.request import urlopen
from urllib.error import HTTPError

from http.server import ThreadingHTTPServer

from cyborg_core.config import BehaviorConfig, CacheConfig, CalendarSource, ServiceConfig
from cyborg_core.server import WEB_ROOT, make_handler
from cyborg_core.service import CyborgService
from cyborg_core.store import LastKnownGoodStore


def _service(tmp_path):
    config = ServiceConfig(
        home_tz="America/Chicago",
        calendars=(CalendarSource("family", "Family", "fixture://family", "#111111"),),
        cache=CacheConfig(tmp_path / "usb" / "lkg.json", tmp_path / "fallback.json"),
        behavior=BehaviorConfig(),
    )
    store = LastKnownGoodStore(tmp_path / "usb" / "lkg.json", tmp_path / "fallback.json")
    return CyborgService(config, store, clock=lambda: datetime.fromisoformat("2026-06-17T09:00:00-05:00"))


def _serve(service):
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(service, web_root=WEB_ROOT))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def test_static_routes_serve_frontend_with_content_types(tmp_path):
    server, thread = _serve(_service(tmp_path))
    try:
        port = server.server_address[1]
        base = f"http://127.0.0.1:{port}"
        cases = {
            "/": "text/html",
            "/index.html": "text/html",
            "/app.js": "application/javascript",
            "/theme.js": "application/javascript",
            "/style.css": "text/css",
        }
        for path, ctype in cases.items():
            resp = urlopen(base + path, timeout=5)
            assert resp.status == 200, path
            assert ctype in resp.headers.get("Content-Type", ""), path
            assert resp.read(), path
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_api_routes_still_work_alongside_static(tmp_path):
    server, thread = _serve(_service(tmp_path))
    try:
        port = server.server_address[1]
        base = f"http://127.0.0.1:{port}"
        agenda = json.loads(urlopen(base + "/api/agenda", timeout=5).read())
        health = json.loads(urlopen(base + "/health", timeout=5).read())
        assert "staleness" in agenda
        assert health["clock"]["home_tz"] == "America/Chicago"
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_path_traversal_is_blocked(tmp_path):
    server, thread = _serve(_service(tmp_path))
    try:
        port = server.server_address[1]
        try:
            urlopen(f"http://127.0.0.1:{port}/../cyborg_core/server.py", timeout=5)
            raised = False
        except HTTPError as exc:
            raised = exc.code == 404
        assert raised, "path traversal should 404"
    finally:
        server.shutdown()
        thread.join(timeout=5)
