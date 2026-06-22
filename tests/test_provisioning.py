from __future__ import annotations

import configparser
from datetime import datetime
import importlib.util
import json
import os
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


def _run_setup_dry(tmp_path: Path) -> subprocess.CompletedProcess[str]:
    # The Pi 5 model needs no USB/blkid probing; only a kiosk-user home lookup.
    fakebin = tmp_path / "bin"
    fakebin.mkdir()
    (fakebin / "getent").write_text(
        '#!/usr/bin/env bash\n'
        'if [[ "$1" == "passwd" && "$2" == "reviewer" ]]; then\n'
        '  echo "reviewer:x:1000:1000:Reviewer:/home/reviewer:/bin/bash"\n'
        '  exit 0\n'
        'fi\n'
        'exit 2\n',
        encoding="utf-8",
    )
    (fakebin / "getent").chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = f"{fakebin}:{env['PATH']}"
    env["CYBORG_KIOSK_USER"] = "reviewer"
    return subprocess.run(
        ["bash", str(ROOT / "scripts" / "setup.sh"), "--dry-run"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


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


def test_cyborg_service_unit_has_required_directives():
    # The validated live unit: runs from the checkout as the kiosk user.
    unit = _unit("cyborg.service")
    assert unit["Unit"]["After"] == "network-online.target"
    assert unit["Unit"]["Wants"] == "network-online.target"
    assert unit["Service"]["ExecStart"] == "/home/pi/onward-cyborg/.venv/bin/python -m cyborg_core --config config.local.toml"
    assert unit["Service"]["WorkingDirectory"] == "/home/pi/onward-cyborg"
    assert unit["Service"]["User"] == "pi"
    assert unit["Service"]["Restart"] == "always"
    assert unit["Install"]["WantedBy"] == "multi-user.target"


def test_optional_appliance_units_remain_available_but_unwired():
    # Screen on/off + shutdown-button units are KEPT in the repo as opt-in features
    # (not installed by setup.sh; not yet hardware-validated). They must still parse.
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
        assert timer["Install"]["WantedBy"] == "timers.target"


def test_xdg_autostart_launcher_is_the_kiosk_entry():
    text = (ROOT / "deploy" / "autostart" / "cyborg-kiosk.desktop").read_text(encoding="utf-8")
    assert "[Desktop Entry]" in text
    assert "X-GNOME-Autostart-enabled=true" in text
    for token in (
        "chromium ",
        "--kiosk",
        "--password-store=basic",
        "--start-fullscreen",
        "http://localhost:8765/",
    ):
        assert token in text, f"launcher missing {token}"
    # Old-model artifacts must be gone from the launcher.
    assert "chromium-browser" not in text
    assert "xrandr" not in text
    assert "--incognito" not in text


def test_setup_script_contract_and_shellcheck_if_available():
    script = ROOT / "scripts" / "setup.sh"
    text = script.read_text(encoding="utf-8")
    # New, validated Pi 5 model.
    assert "set -euo pipefail" in text
    assert "--dry-run" in text
    assert "dtoverlay=vc4-kms-dsi-ili9881-7inch,rotation=90" in text
    assert "autologin-user=${KIOSK_USER}" in text
    assert "deploy/autostart/cyborg-kiosk.desktop" in text
    assert "/etc/systemd/system/cyborg.service" in text
    assert "apt-get install -y chromium" in text
    assert "/opt/cyborg-core/cache" in text or 'CACHE_DIR="${CYBORG_CACHE_DIR:-/opt/cyborg-core/cache}"' in text
    # Old Pi 3B + Acer model must be gone from OPERATIVE code (comments may still
    # name what was dropped, so check non-comment lines only).
    code = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))
    for banned in ("/mnt/cyborg", "gpu_mem", "do_i2c", "agetty", "startx", "openbox-session", "blkid", "xrandr", "chromium-browser"):
        assert banned not in code, f"old-model artifact still operative: {banned}"
    if shutil.which("shellcheck") is None:
        return
    result = subprocess.run(["shellcheck", str(script)], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr


def test_setup_dry_run_generates_kiosk_boot_path_and_service(tmp_path):
    result = _run_setup_dry(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    out = result.stdout
    assert "apt-get install -y chromium" in out
    assert "ensure line in /boot/firmware/config.txt: dtoverlay=vc4-kms-dsi-ili9881-7inch,rotation=90" in out
    assert "ensure line in /etc/lightdm/lightdm.conf: autologin-user=reviewer" in out
    assert "/home/reviewer/.config/autostart/cyborg-kiosk.desktop" in out
    assert "write /etc/systemd/system/cyborg.service" in out
    assert "systemctl enable cyborg.service" in out
    assert "Boot model: lightdm autologin (reviewer)" in out
    # No USB / console-autologin model.
    assert "/mnt/cyborg" not in out
    assert "agetty" not in out


def test_shutdown_button_imports_without_rpi_gpio(monkeypatch):
    monkeypatch.setitem(sys.modules, "RPi", None)
    monkeypatch.setitem(sys.modules, "RPi.GPIO", None)
    spec = importlib.util.spec_from_file_location("shutdown_button_under_test", ROOT / "scripts" / "shutdown_button.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.GPIO is None
    assert module.GPIO_PIN == 17
