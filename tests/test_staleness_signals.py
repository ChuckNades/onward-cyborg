from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from cyborg_core.signals import (
    APP_LOAD,
    FETCH_FAILURE_RECOVERY,
    REFRESH_SIGNAL_RATE_LIMIT,
    SUCCESSFUL_REFRESH,
    SignalLimiter,
)
from cyborg_core.staleness import classify_staleness


BASE = datetime.fromisoformat("2026-06-17T12:00:00-05:00")


def test_staleness_boundaries_and_first_boot_syncing_state():
    assert classify_staleness(now=BASE, last_success=None, home_tz="America/Chicago")["message"] == "waking up / syncing"
    assert classify_staleness(now=BASE, last_success=BASE - timedelta(minutes=14, seconds=59), home_tz="America/Chicago")["tier"] == "fresh"
    stale = classify_staleness(now=BASE, last_success=BASE - timedelta(minutes=15), home_tz="America/Chicago")
    assert stale["tier"] == "stale"
    assert stale["show_chip"] is True
    assert classify_staleness(now=BASE, last_success=BASE - timedelta(hours=6), home_tz="America/Chicago")["tier"] == "stale"
    assert classify_staleness(now=BASE, last_success=BASE - timedelta(hours=6, seconds=1), home_tz="America/Chicago")["tier"] == "on-backup"


def test_system_event_signal_rate_limits_with_injected_clock():
    limiter = SignalLimiter()

    assert limiter.fire(APP_LOAD, BASE) == APP_LOAD
    assert limiter.fire(APP_LOAD, BASE + timedelta(seconds=1)) is None
    assert limiter.fire(SUCCESSFUL_REFRESH, BASE) == SUCCESSFUL_REFRESH
    assert limiter.fire(FETCH_FAILURE_RECOVERY, BASE + REFRESH_SIGNAL_RATE_LIMIT - timedelta(seconds=1)) is None
    assert limiter.fire(FETCH_FAILURE_RECOVERY, BASE + REFRESH_SIGNAL_RATE_LIMIT) == FETCH_FAILURE_RECOVERY


def test_signaling_source_does_not_reference_event_content_fields():
    text = Path("cyborg_core/signals.py").read_text(encoding="utf-8").lower()
    forbidden = [
        "summary",
        "title",
        "description",
        "location",
        "attendee",
        "categories",
        "organizer",
        "uid",
        "dtstart",
        "dtend",
    ]

    assert [word for word in forbidden if word in text] == []
