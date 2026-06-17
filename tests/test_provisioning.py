from __future__ import annotations

import configparser
from datetime import datetime
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import threading
from urllib.request import urlopen

from http.server import ThreadingHTTPServer

from cyborg_core.__main__ import run_cycles
from cyborg_core.config import BehaviorConfig, CacheConfig, CalendarSource, ServiceConfig
from cyborg_core.server import make_handler
from cyborg_core.service import CyborgService
from cyborg_core.store import LastKnownGoodStore

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures"
SYSTEMD = ROOT / "deploy" / "systemd"


class FrozenClock:
    def __init__(self, value: str):
        self.value = datetime.fromisoformat(value)

    def __call__(self):
        return self.value


def _config(tmp_path: Path) -> ServiceConfig:
    return ServiceConfig(
        home_tz="America/Chicago",
        calendars=(CalendarSource("family", "Family", "fixture://family", "#111111"),),
        cache=CacheConfig(tmp_path / "usb" / "lkg.json", tmp_path / "fallback.json"),
        behavior=BehaviorConfig(),
        poll_seconds=300,
        lookahead_days=10,
    )


def _fetcher(url: str) -> bytes:
    assert url == "fixture://family"
    return (FIXTURES / "all_day.ics").read_bytes()


def _unit(name: str) -> configparser.ConfigParser:
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str
    parser.read(SYSTEMD / name)
    return parser


def test_run_cycles_refreshes_deterministically_and_serves_agenda(tmp_path):
    (tmp_path / "usb").mkdir()
    service = CyborgService(
        _config(tmp_path),
        LastKnownGoodStore(tmp_path / "usb" / "lkg.json", tmp_path / "fallback.json"),
        clock=FrozenClock("2026-06-17T09:00:00-05:00"),
        fetcher=_fetcher,
    )
    sleeps: list[float] = []

    assert run_cycles(service, 3, sleep_fn=sleeps.append) == 3
    assert sleeps == [300, 300, 300]

    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(service))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        payload = json.loads(urlopen(f"http://127.0.0.1:{server.server_address[1]}/api/agenda", timeout=5).read())
    finally:
        server.shutdown()
        thread.join(timeout=5)

    assert service._cycle == 3
    assert payload["events"]
    assert payload["events"][0]["title"] == "Field Day"


def test_systemd_units_have_required_directives():
    fetch = _unit("cyborg-fetch.service")
    assert fetch["Unit"]["After"] == "network-online.target"
    assert fetch["Unit"]["Wants"] == "network-online.target"
    assert fetch["Service"]["ExecStart"] == "/opt/cyborg-core/.venv/bin/python -m cyborg_core --config /etc/cyborg/config.local.toml"
    assert fetch["Service"]["Restart"] == "always"
    assert fetch["Service"]["RestartSec"] == "5"
    assert fetch["Service"]["User"] == "cyborg"
    assert fetch["Service"]["WorkingDirectory"] == "/opt/cyborg-core"
    assert fetch["Service"]["NoNewPrivileges"] == "true"

    for name in (
        "cyborg-screen-off.service",
        "cyborg-screen-on.service",
        "cyborg-shutdown-button.service",
    ):
        unit = _unit(name)
        assert unit["Service"]["ExecStart"]

    for name in ("cyborg-screen-off.timer", "cyborg-screen-on.timer"):
        timer = _unit(name)
        assert timer["Timer"]["OnCalendar"]
        assert timer["Timer"]["Persistent"] == "true"
        assert timer["Install"]["WantedBy"] == "timers.target"


def test_openbox_autostart_contains_portrait_touch_and_exact_chromium_flags():
    text = (ROOT / "deploy" / "openbox" / "autostart").read_text(encoding="utf-8")
    assert "xrandr --output \"$HDMI_OUTPUT\" --rotate left" in text
    assert '"Coordinate Transformation Matrix" 0 -1 1 1 0 0 0 0 1' in text
    assert "unclutter" in text
    assert "http://127.0.0.1:8765/" in text
    for flag in (
        "--kiosk",
        "--noerrdialogs",
        "--disable-infobars",
        "--incognito",
        "--disable-extensions",
        "--disable-gpu-compositing",
        "--disable-features=Translate",
        "--check-for-update-interval=31536000",
        "--overscroll-history-navigation=0",
        "--force-device-scale-factor=1",
    ):
        assert flag in text


def test_setup_script_contract_and_shellcheck_if_available():
    script = ROOT / "scripts" / "setup.sh"
    text = script.read_text(encoding="utf-8")
    assert "set -euo pipefail" in text
    assert "--dry-run" in text
    assert "UUID=${USB_UUID} ${MOUNT_POINT} ext4 nofail,noatime 0 2" in text
    assert "gpu_mem=128" in text
    assert "raspi-config nonint do_i2c 0" in text
    assert "--no-index --find-links" in text
    assert "vcgencmd get_throttled" in text
    if shutil.which("shellcheck") is None:
        return
    result = subprocess.run(["shellcheck", str(script)], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr


def test_shutdown_button_imports_without_rpi_gpio(monkeypatch):
    monkeypatch.setitem(sys.modules, "RPi", None)
    monkeypatch.setitem(sys.modules, "RPi.GPIO", None)
    spec = importlib.util.spec_from_file_location("shutdown_button_under_test", ROOT / "scripts" / "shutdown_button.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.GPIO is None
    assert module.GPIO_PIN == 17
