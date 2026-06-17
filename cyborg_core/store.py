from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import tempfile
from typing import Any


@dataclass(frozen=True)
class StoreStatus:
    path: str
    using_fallback: bool
    usb_available: bool
    writable: bool
    message: str


class LastKnownGoodStore:
    def __init__(self, primary_path: Path, fallback_path: Path):
        self.primary_path = primary_path
        self.fallback_path = fallback_path
        self._last_serialized: str | None = None
        self._last_cycle_written: object | None = None

    def status(self) -> StoreStatus:
        writable = self._primary_writable()
        path = self.primary_path if writable or self.primary_path.exists() else self.fallback_path
        return StoreStatus(
            path=str(path),
            using_fallback=not writable,
            usb_available=self.primary_path.exists() or self.primary_path.parent.exists(),
            writable=writable,
            message="usb cache writable" if writable else "usb cache unavailable; using microSD fallback",
        )

    def read(self) -> dict[str, Any] | None:
        for path in (self.primary_path, self.fallback_path):
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        return None

    def write_if_changed(self, payload: dict[str, Any], *, cycle_id: object) -> bool:
        if self._last_cycle_written == cycle_id:
            return False
        if not self._primary_writable():
            return False
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        if serialized == self._last_serialized:
            return False
        if self.primary_path.exists():
            current = self.primary_path.read_text(encoding="utf-8")
            try:
                current = json.dumps(json.loads(current), sort_keys=True, separators=(",", ":"))
            except json.JSONDecodeError:
                pass
            if current == serialized:
                self._last_serialized = serialized
                return False
        self._atomic_write(self.primary_path, serialized + "\n")
        self._last_serialized = serialized
        self._last_cycle_written = cycle_id
        return True

    def _primary_writable(self) -> bool:
        if not self.primary_path.parent.exists() or not self.primary_path.parent.is_dir():
            return False
        try:
            with tempfile.NamedTemporaryFile(dir=self.primary_path.parent, delete=True):
                pass
            return True
        except OSError:
            return False

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as tmp:
                tmp.write(content)
                tmp.flush()
                os.fsync(tmp.fileno())
            os.replace(tmp_name, path)
            dir_fd = os.open(path.parent, os.O_DIRECTORY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except Exception:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass
            raise


def cache_payload(*, events: list[dict[str, Any]], calendars: dict[str, dict[str, str]], fetched_at: datetime) -> dict[str, Any]:
    return {
        "version": 1,
        "fetched_at": fetched_at.isoformat(),
        "events": events,
        "calendars": calendars,
    }
