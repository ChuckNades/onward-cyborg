from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

FRESH_LIMIT = timedelta(minutes=15)
BACKUP_LIMIT = timedelta(hours=6)


def classify_staleness(*, now: datetime, last_success: datetime | None, home_tz: str) -> dict[str, object]:
    if last_success is None:
        return {
            "tier": "syncing",
            "show_chip": True,
            "message": "waking up / syncing",
            "age_seconds": None,
        }
    tz = ZoneInfo(home_tz)
    local_now = _local(now, tz)
    local_success = _local(last_success, tz)
    age = max(timedelta(0), local_now - local_success)
    if age < FRESH_LIMIT:
        tier = "fresh"
        show_chip = False
    elif age <= BACKUP_LIMIT:
        tier = "stale"
        show_chip = True
    else:
        tier = "on-backup"
        show_chip = True
    return {
        "tier": tier,
        "show_chip": show_chip,
        "message": tier,
        "age_seconds": int(age.total_seconds()),
    }


def _local(value: datetime, tz: ZoneInfo) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=tz)
    return value.astimezone(tz)
