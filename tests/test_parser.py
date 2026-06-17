from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from cyborg_core.config import BehaviorConfig, CalendarSource
from cyborg_core.parser import merge_agenda, normalize_calendar, select_next

FIXTURES = Path(__file__).parent / "fixtures"


def source(id_: str = "family", color: str = "#123456") -> CalendarSource:
    return CalendarSource(id=id_, name=id_.title(), url=f"fixture://{id_}", color=color)


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def now(value: str) -> datetime:
    return datetime.fromisoformat(value)


def normalize(name: str, *, at: str = "2026-06-17T07:00:00-05:00"):
    return normalize_calendar(
        fixture(name),
        source(),
        home_tz="America/Chicago",
        now=now(at),
        lookahead_days=10,
        behavior=BehaviorConfig(),
    )


def test_all_day_event_normalizes_as_all_day_and_next_orders_before_timed_today():
    all_day = normalize("all_day.ics")
    timed = normalize("overlapping.ics")
    events = all_day + timed

    assert all_day[0].all_day is True
    assert all_day[0].start == "2026-06-17T00:00:00-05:00"
    assert select_next(events, now=now("2026-06-17T09:00:00-05:00"), home_tz="America/Chicago")["title"] == "Field Day"


def test_multi_day_spanning_event_is_marked_multi_day():
    events = normalize("multi_day.ics")

    assert len(events) == 1
    assert events[0].multi_day is True
    assert events[0].start == "2026-06-17T18:00:00-05:00"
    assert events[0].end == "2026-06-18T20:00:00-05:00"


def test_overlapping_events_are_preserved_and_sorted():
    events = normalize("overlapping.ics")

    assert [event.title for event in events] == ["Math", "Dentist"]
    assert events[0].end > events[1].start


def test_recurring_rrule_expands_occurrences():
    events = normalize("recurring.ics")

    assert [event.start for event in events] == [
        "2026-06-17T08:00:00-05:00",
        "2026-06-18T08:00:00-05:00",
        "2026-06-19T08:00:00-05:00",
    ]


def test_declined_hidden_and_tentative_dimmed_flag_is_config_flippable():
    default = normalize("declined_tentative.ics")
    visible_declined = normalize_calendar(
        fixture("declined_tentative.ics"),
        source(),
        home_tz="America/Chicago",
        now=now("2026-06-17T07:00:00-05:00"),
        lookahead_days=10,
        behavior=BehaviorConfig(show_tentative=False, hide_declined=False),
    )

    assert [event.title for event in default] == ["Maybe"]
    assert default[0].tentative is True
    assert default[0].dimmed is True
    assert [event.title for event in visible_declined] == ["Nope", "Maybe"]
    assert visible_declined[1].dimmed is False


def test_timezone_normalizes_to_home_tz_across_dst_boundary():
    events = normalize_calendar(
        fixture("timezone_dst.ics"),
        source(),
        home_tz="America/Chicago",
        now=datetime(2026, 3, 7, 12, tzinfo=ZoneInfo("America/Chicago")),
        lookahead_days=2,
        behavior=BehaviorConfig(),
    )

    assert events[0].start == "2026-03-08T00:30:00-06:00"
    assert events[0].end == "2026-03-08T01:30:00-06:00"


def test_two_calendars_merge_with_config_colors_not_ics_values():
    merged = merge_agenda(
        {
            source("family", "#111111"): fixture("all_day.ics"),
            source("school", "#222222"): fixture("overlapping.ics"),
        },
        home_tz="America/Chicago",
        now=now("2026-06-17T07:00:00-05:00"),
        lookahead_days=10,
        behavior=BehaviorConfig(),
    )

    assert {event.calendar_id for event in merged} == {"family", "school"}
    assert {event.color for event in merged} == {"#111111", "#222222"}
