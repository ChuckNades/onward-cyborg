"""Grep-able PRD section 13 invariant test for the FRONTEND theming surface.

theme.js is the only place theming / celebration / BOOYAH-audio is allowed to live, and it
may consume ONLY system state (staleness tier + the three system-event signal strings). This
test FAILS if theme.js references any calendar event-content field, structurally proving the
theming layer cannot branch on event content. It also locks the DOM-light / animation-free /
no-framework budget from the Pi 3B performance contract (section I).
"""
from __future__ import annotations

from pathlib import Path
import re

WEB = Path(__file__).resolve().parents[1] / "web"

# Event-content fields the theming surface must never read or branch on.
FORBIDDEN_CONTENT_FIELDS = [
    "summary",
    "title",
    "description",
    "location",
    "attendee",
    "categories",
    "organizer",
    "dtstart",
    "dtend",
]


def _read(name: str) -> str:
    return (WEB / name).read_text(encoding="utf-8")


def test_theme_js_never_references_event_content_fields():
    text = _read("theme.js").lower()
    hits = [field for field in FORBIDDEN_CONTENT_FIELDS if re.search(r"\b" + re.escape(field) + r"\b", text)]
    assert hits == [], f"theme.js must not branch on event content; found: {hits}"


def test_theme_js_does_not_index_event_or_agenda_collections():
    text = _read("theme.js").lower()
    # The theming surface must not touch the event/agenda data structures at all.
    for token in ["events", "agenda", "ev.", ".calendar_id", "event["]:
        assert token not in text, f"theme.js must not access event data ({token})"


def test_theme_js_audio_is_gated_on_system_signals_only():
    text = _read("theme.js")
    assert "SYSTEM_SIGNALS" in text
    assert 'SYSTEM_SIGNALS.indexOf(systemEvent) === -1' in text
    # The play call is reached only after the system-signal guard.
    guard = text.index("SYSTEM_SIGNALS.indexOf")
    play = text.index("playBooyah()", text.index("function signal"))
    assert guard < play, "BOOYAH must be gated by the system-signal check"


def test_index_html_has_no_framework_or_cdn_scripts():
    html = _read("index.html")
    scripts = re.findall(r"<script[^>]*src=[\"']([^\"']+)[\"']", html, flags=re.IGNORECASE)
    for src in scripts:
        assert src.startswith("/") and "//" not in src, f"only local scripts allowed: {src}"
    lowered = html.lower()
    for banned in ["cdn", "react", "vue", "angular", "jquery", "http://", "https://"]:
        assert banned not in lowered, f"no framework/CDN allowed: {banned}"


def test_style_css_is_animation_free():
    css = _read("style.css").lower()
    for banned in ["@keyframes", "animation:", "animation-name", "transition:"]:
        assert banned not in css, f"animation-free budget violated: {banned}"


def test_staleness_label_is_computed_inside_theme_from_system_time_only():
    # Closes the staleChip-label loophole (cross-vendor review, cycle 2): the theming surface
    # must build its 'updated' label from SYSTEM time itself, not accept caller free-text that
    # could carry event content.
    theme = _read("theme.js")
    app = _read("app.js")
    assert "function updatedLabel" in theme, "theme.js must own the label computation"
    assert "Date.parse" in theme and "offsetMinutes" in theme, "label must derive from system time"
    m = re.search(r"CyborgTheme\.staleChip\(([^)]*)\)", app)
    assert m, "app.js must call CyborgTheme.staleChip"
    args = m.group(1)
    assert "tier" in args, "first arg is the system staleness tier"
    for token in ["title", "summary", "ev.", "event", ".color", "events"]:
        assert token not in args, f"theming call must not pass event data: {token}"


def test_app_js_caps_the_dom_with_a_named_constant():
    app = _read("app.js")
    assert "MAX_VISIBLE_ROWS" in app
    m = re.search(r"MAX_VISIBLE_ROWS\s*=\s*(\d+)", app)
    assert m and int(m.group(1)) <= 30, "agenda must be capped to a small DOM-light row count"
    assert "innerHTML" not in app, "render must be DOM-light (textContent only, no innerHTML)"
