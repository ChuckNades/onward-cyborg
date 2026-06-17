from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

APP_LOAD = "app-load"
SUCCESSFUL_REFRESH = "successful-refresh"
FETCH_FAILURE_RECOVERY = "fetch-failure-recovery"
SYSTEM_EVENTS = frozenset({APP_LOAD, SUCCESSFUL_REFRESH, FETCH_FAILURE_RECOVERY})
REFRESH_SIGNAL_RATE_LIMIT = timedelta(minutes=10)


@dataclass
class SignalLimiter:
    app_load_sent: bool = False
    last_refresh_signal_at: datetime | None = None
    pending: str | None = None

    def fire(self, system_event: str, now: datetime) -> str | None:
        if system_event not in SYSTEM_EVENTS:
            raise ValueError(f"unknown system event: {system_event}")
        if system_event == APP_LOAD:
            if self.app_load_sent:
                return None
            self.app_load_sent = True
            self.pending = system_event
            return system_event
        if (
            self.last_refresh_signal_at is not None
            and now - self.last_refresh_signal_at < REFRESH_SIGNAL_RATE_LIMIT
        ):
            return None
        self.last_refresh_signal_at = now
        self.pending = system_event
        return system_event

    def consume_pending(self) -> str | None:
        signal = self.pending
        self.pending = None
        return signal
