from __future__ import annotations

import argparse
import logging
import socket
import subprocess
import threading
import time
from collections.abc import Callable
from pathlib import Path

from .config import load_config
from .server import serve
from .service import CyborgService
from .store import LastKnownGoodStore

LOG = logging.getLogger("cyborg_core")


def network_check(host: str = "1.1.1.1", port: int = 53, timeout: float = 3.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def undervoltage_check() -> str:
    try:
        result = subprocess.run(
            ["vcgencmd", "get_throttled"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return f"unavailable: {exc.__class__.__name__}"

    output = (result.stdout or result.stderr).strip()
    if "=" in output:
        return output.split("=", 1)[1].strip()
    return output or f"unavailable: exit {result.returncode}"


def run_cycles(
    service: CyborgService,
    n: int | None,
    sleep_fn: Callable[[float], object] = time.sleep,
) -> int:
    completed = 0
    while n is None or completed < n:
        sleep_fn(service.config.poll_seconds)
        try:
            service.refresh_once()
        except Exception:
            LOG.exception("refresh cycle failed")
        completed += 1
    return completed


def build_service(config_path: str | Path) -> CyborgService:
    config = load_config(config_path)
    store = LastKnownGoodStore(config.cache.primary_path, config.cache.fallback_path)
    return CyborgService(
        config,
        store,
        network_check=network_check,
        undervoltage_check=undervoltage_check,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m cyborg_core")
    parser.add_argument("--config", required=True, help="Path to config.local.toml")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    service = build_service(args.config)
    service.refresh_once()

    poller = threading.Thread(target=run_cycles, args=(service, None), daemon=True)
    poller.start()
    serve(service)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
