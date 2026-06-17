from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib


@dataclass(frozen=True)
class CalendarSource:
    id: str
    name: str
    url: str
    color: str


@dataclass(frozen=True)
class BehaviorConfig:
    show_tentative: bool = True
    hide_declined: bool = True


@dataclass(frozen=True)
class CacheConfig:
    primary_path: Path
    fallback_path: Path


@dataclass(frozen=True)
class ServiceConfig:
    home_tz: str
    calendars: tuple[CalendarSource, ...]
    cache: CacheConfig
    behavior: BehaviorConfig = BehaviorConfig()
    poll_seconds: int = 300
    lookahead_days: int = 45
    host: str = "127.0.0.1"
    port: int = 8765


def load_config(path: str | Path) -> ServiceConfig:
    raw = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    service = raw.get("service", {})
    cache = raw.get("cache", {})
    behavior = raw.get("behavior", {})
    calendars = tuple(
        CalendarSource(
            id=str(item["id"]),
            name=str(item["name"]),
            url=str(item["url"]),
            color=str(item["color"]),
        )
        for item in raw.get("calendars", [])
    )
    if not calendars:
        raise ValueError("config must define at least one calendar")
    return ServiceConfig(
        home_tz=str(service.get("home_tz", "America/Chicago")),
        poll_seconds=int(service.get("poll_seconds", 300)),
        lookahead_days=int(service.get("lookahead_days", 45)),
        host=str(service.get("host", "127.0.0.1")),
        port=int(service.get("port", 8765)),
        calendars=calendars,
        cache=CacheConfig(
            primary_path=Path(cache["primary_path"]),
            fallback_path=Path(cache["fallback_path"]),
        ),
        behavior=BehaviorConfig(
            show_tentative=bool(behavior.get("show_tentative", True)),
            hide_declined=bool(behavior.get("hide_declined", True)),
        ),
    )
