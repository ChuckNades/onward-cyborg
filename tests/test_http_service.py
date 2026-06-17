from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import threading
from urllib.request import urlopen

from cyborg_core.config import BehaviorConfig, CacheConfig, CalendarSource, ServiceConfig
from cyborg_core.server import make_handler
from cyborg_core.service import CyborgService
from cyborg_core.signals import APP_LOAD
from cyborg_core.store import LastKnownGoodStore
from http.server import ThreadingHTTPServer

FIXTURES = Path(__file__).parent / "fixtures"


class FrozenClock:
    def __init__(self, value: str):
        self.value = datetime.fromisoformat(value)

    def __call__(self):
        return self.value


def config(tmp_path):
    return ServiceConfig(
        home_tz="America/Chicago",
        calendars=(
            CalendarSource("family", "Family", "fixture://family", "#111111"),
            CalendarSource("school", "School", "fixture://school", "#222222"),
        ),
        cache=CacheConfig(tmp_path / "usb" / "lkg.json", tmp_path / "fallback.json"),
        behavior=BehaviorConfig(),
        lookahead_days=10,
    )


def fetcher(url: str) -> bytes:
    return {
        "fixture://family": (FIXTURES / "all_day.ics").read_bytes(),
        "fixture://school": (FIXTURES / "overlapping.ics").read_bytes(),
    }[url]


def test_refresh_and_agenda_response_include_next_staleness_colors_and_signal(tmp_path):
    (tmp_path / "usb").mkdir()
    service = CyborgService(
        config(tmp_path),
        LastKnownGoodStore(tmp_path / "usb" / "lkg.json", tmp_path / "fallback.json"),
        clock=FrozenClock("2026-06-17T09:00:00-05:00"),
        fetcher=fetcher,
    )
    service.signal_limiter.fire(APP_LOAD, datetime.fromisoformat("2026-06-17T08:59:00-05:00"))

    assert service.refresh_once() is True
    agenda = service.agenda_response()

    assert agenda["next"]["title"] == "Field Day"
    assert agenda["staleness"]["tier"] == "fresh"
    assert agenda["calendars"]["family"]["color"] == "#111111"
    assert agenda["pending_signal"] in {APP_LOAD, "successful-refresh"}


def test_health_surfaces_usb_lkg_clock_network_and_undervoltage(tmp_path):
    (tmp_path / "usb").mkdir()
    service = CyborgService(
        config(tmp_path),
        LastKnownGoodStore(tmp_path / "usb" / "lkg.json", tmp_path / "fallback.json"),
        clock=FrozenClock("2026-06-17T09:00:00-05:00"),
        fetcher=fetcher,
        network_check=lambda: False,
        undervoltage_check=lambda: "0x0",
    )
    service.refresh_once()

    health = service.health_response()

    assert health["fetch"]["ok"] is True
    assert health["usb"]["writable"] is True
    assert health["lkg"]["available"] is True
    assert health["clock"]["home_tz"] == "America/Chicago"
    assert health["network_reachable"] is False
    assert health["undervoltage"] == "0x0"


def test_http_endpoints_are_real_localhost_json_endpoints(tmp_path):
    (tmp_path / "usb").mkdir()
    service = CyborgService(
        config(tmp_path),
        LastKnownGoodStore(tmp_path / "usb" / "lkg.json", tmp_path / "fallback.json"),
        clock=FrozenClock("2026-06-17T09:00:00-05:00"),
        fetcher=fetcher,
    )
    service.refresh_once()
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(service))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        agenda = json.loads(urlopen(f"http://127.0.0.1:{port}/api/agenda", timeout=5).read())
        health = json.loads(urlopen(f"http://127.0.0.1:{port}/health", timeout=5).read())
    finally:
        server.shutdown()
        thread.join(timeout=5)

    assert agenda["events"]
    assert health["clock"]["home_tz"] == "America/Chicago"
