from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable
from urllib.request import urlopen

from .config import ServiceConfig
from .parser import merge_agenda, select_next
from .signals import FETCH_FAILURE_RECOVERY, SUCCESSFUL_REFRESH, SignalLimiter
from .staleness import classify_staleness
from .store import LastKnownGoodStore, cache_payload

Clock = Callable[[], datetime]
Fetcher = Callable[[str], bytes]


@dataclass
class FetchStatus:
    ok: bool = False
    last_success: datetime | None = None
    last_failure: datetime | None = None
    last_error: str | None = None
    recovered_from_failure: bool = False


class CyborgService:
    def __init__(
        self,
        config: ServiceConfig,
        store: LastKnownGoodStore,
        *,
        clock: Clock | None = None,
        fetcher: Fetcher | None = None,
        signal_limiter: SignalLimiter | None = None,
        network_check: Callable[[], bool] | None = None,
        undervoltage_check: Callable[[], str] | None = None,
    ):
        self.config = config
        self.store = store
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.fetcher = fetcher or default_fetcher
        self.signal_limiter = signal_limiter or SignalLimiter()
        self.network_check = network_check or (lambda: True)
        self.undervoltage_check = undervoltage_check or (lambda: "unknown")
        self.fetch_status = FetchStatus()
        self._cycle = 0

    def refresh_once(self) -> bool:
        self._cycle += 1
        now = self.clock()
        try:
            fetched = {source: self.fetcher(source.url) for source in self.config.calendars}
            events = merge_agenda(
                fetched,
                home_tz=self.config.home_tz,
                now=now,
                lookahead_days=self.config.lookahead_days,
                behavior=self.config.behavior,
            )
            calendars = {
                source.id: {"name": source.name, "color": source.color}
                for source in self.config.calendars
            }
            payload = cache_payload(
                events=[event.to_json() for event in events],
                calendars=calendars,
                fetched_at=now,
            )
            self.store.write_if_changed(payload, cycle_id=self._cycle)
            recovered = self.fetch_status.last_failure is not None and not self.fetch_status.ok
            self.fetch_status = FetchStatus(ok=True, last_success=now, recovered_from_failure=recovered)
            self.signal_limiter.fire(FETCH_FAILURE_RECOVERY if recovered else SUCCESSFUL_REFRESH, now)
            return True
        except Exception as exc:
            self.fetch_status.ok = False
            self.fetch_status.last_failure = now
            self.fetch_status.last_error = f"{exc.__class__.__name__}: {exc}"
            return False

    def agenda_response(self) -> dict[str, object]:
        now = self.clock()
        cached = self.store.read()
        if cached is None:
            events: list[dict[str, object]] = []
            calendars = {
                source.id: {"name": source.name, "color": source.color}
                for source in self.config.calendars
            }
            fetched_at = None
        else:
            events = list(cached.get("events", []))
            calendars = dict(cached.get("calendars", {}))
            fetched_raw = cached.get("fetched_at")
            fetched_at = datetime.fromisoformat(fetched_raw) if fetched_raw else None
        next_event = select_next_events_from_json(events, now=now, home_tz=self.config.home_tz)
        return {
            "now": now.isoformat(),
            "home_tz": self.config.home_tz,
            "events": events,
            "next": next_event,
            "staleness": classify_staleness(now=now, last_success=fetched_at, home_tz=self.config.home_tz),
            "calendars": calendars,
            "pending_signal": self.signal_limiter.consume_pending(),
        }

    def health_response(self) -> dict[str, object]:
        now = self.clock()
        cached = self.store.read()
        fetched_raw = cached.get("fetched_at") if cached else None
        fetched_at = datetime.fromisoformat(fetched_raw) if fetched_raw else None
        store_status = self.store.status()
        return {
            "ok": self.fetch_status.ok or cached is not None,
            "fetch": {
                "ok": self.fetch_status.ok,
                "last_success": self.fetch_status.last_success.isoformat() if self.fetch_status.last_success else None,
                "last_failure": self.fetch_status.last_failure.isoformat() if self.fetch_status.last_failure else None,
                "last_error": self.fetch_status.last_error,
            },
            "usb": {
                "path": store_status.path,
                "available": store_status.usb_available,
                "writable": store_status.writable,
                "using_fallback": store_status.using_fallback,
                "message": store_status.message,
            },
            "lkg": {
                "available": cached is not None,
                "fetched_at": fetched_raw,
                "staleness": classify_staleness(now=now, last_success=fetched_at, home_tz=self.config.home_tz),
            },
            "clock": {"now": now.isoformat(), "home_tz": self.config.home_tz},
            "network_reachable": self.network_check(),
            "undervoltage": self.undervoltage_check(),
        }


def default_fetcher(url: str) -> bytes:
    with urlopen(url, timeout=20) as response:
        return response.read()


def select_next_events_from_json(events: list[dict[str, object]], *, now: datetime, home_tz: str) -> dict[str, object] | None:
    from .parser import NormalizedEvent

    normalized = [
        NormalizedEvent(
            id=str(event["id"]),
            calendar_id=str(event["calendar_id"]),
            calendar_name=str(event["calendar_name"]),
            color=str(event["color"]),
            title=str(event["title"]),
            start=str(event["start"]),
            end=str(event["end"]),
            start_date=str(event["start_date"]),
            end_date=str(event["end_date"]),
            all_day=bool(event["all_day"]),
            multi_day=bool(event["multi_day"]),
            tentative=bool(event["tentative"]),
            dimmed=bool(event["dimmed"]),
            status=str(event["status"]),
        )
        for event in events
    ]
    return select_next(normalized, now=now, home_tz=home_tz)
