from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from hashlib import sha1
from typing import Any
from zoneinfo import ZoneInfo

from icalendar import Calendar
import recurring_ical_events

from .config import BehaviorConfig, CalendarSource


@dataclass(frozen=True)
class NormalizedEvent:
    id: str
    calendar_id: str
    calendar_name: str
    color: str
    title: str
    start: str
    end: str
    start_date: str
    end_date: str
    all_day: bool
    multi_day: bool
    tentative: bool
    dimmed: bool
    status: str

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "calendar_id": self.calendar_id,
            "calendar_name": self.calendar_name,
            "color": self.color,
            "title": self.title,
            "start": self.start,
            "end": self.end,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "all_day": self.all_day,
            "multi_day": self.multi_day,
            "tentative": self.tentative,
            "dimmed": self.dimmed,
            "status": self.status,
        }


def normalize_calendar(
    ics_bytes: bytes,
    source: CalendarSource,
    *,
    home_tz: str,
    now: datetime,
    lookahead_days: int,
    behavior: BehaviorConfig,
) -> list[NormalizedEvent]:
    tz = ZoneInfo(home_tz)
    window_start = _aware(now, tz) - timedelta(days=1)
    window_end = _aware(now, tz) + timedelta(days=lookahead_days)
    calendar = Calendar.from_ical(ics_bytes)
    events: list[NormalizedEvent] = []
    for component in recurring_ical_events.of(calendar).between(window_start, window_end):
        if _is_declined(component) and behavior.hide_declined:
            continue
        event = _normalize_event(component, source, tz, behavior)
        if event is not None:
            events.append(event)
    return sorted(events, key=event_sort_key)


def merge_agenda(
    calendars: dict[CalendarSource, bytes],
    *,
    home_tz: str,
    now: datetime,
    lookahead_days: int,
    behavior: BehaviorConfig,
) -> list[NormalizedEvent]:
    merged: list[NormalizedEvent] = []
    for source, ics_bytes in calendars.items():
        merged.extend(
            normalize_calendar(
                ics_bytes,
                source,
                home_tz=home_tz,
                now=now,
                lookahead_days=lookahead_days,
                behavior=behavior,
            )
        )
    return sorted(merged, key=event_sort_key)


def select_next(events: list[NormalizedEvent], *, now: datetime, home_tz: str) -> dict[str, Any] | None:
    tz = ZoneInfo(home_tz)
    local_now = _aware(now, tz)
    today = local_now.date()
    candidates: list[tuple[tuple[int, datetime, str], NormalizedEvent]] = []
    for event in events:
        start = datetime.fromisoformat(event.start)
        end = datetime.fromisoformat(event.end)
        if event.all_day and date.fromisoformat(event.start_date) <= today < date.fromisoformat(event.end_date):
            candidates.append(((0, local_now, event.id), event))
        elif start >= local_now:
            same_day_priority = 0 if event.all_day and start.date() == today else 1
            candidates.append(((same_day_priority, start, event.id), event))
    if not candidates:
        return None
    return min(candidates, key=lambda item: item[0])[1].to_json()


def event_sort_key(event: NormalizedEvent) -> tuple[str, int, str, str]:
    start = datetime.fromisoformat(event.start)
    return (
        start.date().isoformat(),
        0 if event.all_day else 1,
        event.start,
        event.id,
    )


def _normalize_event(
    component: Any,
    source: CalendarSource,
    tz: ZoneInfo,
    behavior: BehaviorConfig,
) -> NormalizedEvent | None:
    raw_start = component.decoded("dtstart")
    raw_end = component.decoded("dtend", None)
    all_day = isinstance(raw_start, date) and not isinstance(raw_start, datetime)
    if all_day:
        start_date = raw_start
        end_date = raw_end if isinstance(raw_end, date) and not isinstance(raw_end, datetime) else start_date + timedelta(days=1)
        start_dt = datetime.combine(start_date, time.min, tzinfo=tz)
        end_dt = datetime.combine(end_date, time.min, tzinfo=tz)
    else:
        start_dt = _aware(raw_start, tz)
        if raw_end is None:
            raw_end = start_dt
        end_dt = _aware(raw_end, tz)
        start_date = start_dt.date()
        end_date = end_dt.date()
        if end_dt.time() != time.min or end_dt.date() == start_dt.date():
            end_date = end_dt.date() + timedelta(days=1) if end_dt.date() > start_dt.date() else end_dt.date()
    if end_dt < start_dt:
        return None
    status = str(component.get("STATUS", "CONFIRMED")).upper()
    tentative = status == "TENTATIVE" or _has_attendee_partstat(component, "TENTATIVE")
    dimmed = tentative and behavior.show_tentative
    occurrence = component.get("RECURRENCE-ID", component.get("UID", ""))
    stable = "|".join([source.id, str(component.get("UID", "")), str(occurrence), start_dt.isoformat()])
    title = str(component.get("SUMMARY", "Untitled"))
    return NormalizedEvent(
        id=sha1(stable.encode("utf-8")).hexdigest()[:16],
        calendar_id=source.id,
        calendar_name=source.name,
        color=source.color,
        title=title,
        start=start_dt.isoformat(),
        end=end_dt.isoformat(),
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        all_day=all_day,
        multi_day=end_dt.date() > start_dt.date() if not all_day else (end_date - start_date).days > 1,
        tentative=tentative,
        dimmed=dimmed,
        status=status,
    )


def _aware(value: date | datetime, tz: ZoneInfo) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=tz)
        return value.astimezone(tz)
    return datetime.combine(value, time.min, tzinfo=tz)


def _is_declined(component: Any) -> bool:
    if str(component.get("STATUS", "")).upper() == "CANCELLED":
        return True
    return _has_attendee_partstat(component, "DECLINED")


def _has_attendee_partstat(component: Any, value: str) -> bool:
    attendees = component.get("ATTENDEE", [])
    if not isinstance(attendees, list):
        attendees = [attendees]
    for attendee in attendees:
        params = getattr(attendee, "params", {})
        if str(params.get("PARTSTAT", "")).upper() == value:
            return True
    return False
