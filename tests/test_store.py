from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path

from cyborg_core.store import LastKnownGoodStore, cache_payload


def payload(title: str = "A"):
    return cache_payload(
        events=[{"title": title}],
        calendars={"family": {"name": "Family", "color": "#123456"}},
        fetched_at=datetime(2026, 6, 17, 12, tzinfo=timezone.utc),
    )


def test_atomic_replace_writes_final_file_and_uses_os_replace(tmp_path, monkeypatch):
    primary = tmp_path / "usb" / "lkg.json"
    primary.parent.mkdir()
    store = LastKnownGoodStore(primary, tmp_path / "fallback.json")
    calls = []
    real_replace = os.replace

    def spy_replace(src, dst):
        calls.append((Path(src), Path(dst)))
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", spy_replace)

    assert store.write_if_changed(payload(), cycle_id=1) is True
    assert calls and calls[0][1] == primary
    assert json.loads(primary.read_text(encoding="utf-8"))["events"][0]["title"] == "A"
    assert not list(primary.parent.glob("*.tmp"))


def test_change_gated_frequency_only_writes_changed_data_once_per_cycle(tmp_path):
    primary = tmp_path / "usb" / "lkg.json"
    primary.parent.mkdir()
    store = LastKnownGoodStore(primary, tmp_path / "fallback.json")

    assert store.write_if_changed(payload("A"), cycle_id=1) is True
    assert store.write_if_changed(payload("B"), cycle_id=1) is False
    assert store.write_if_changed(payload("A"), cycle_id=2) is False
    assert store.write_if_changed(payload("B"), cycle_id=3) is True


def test_usb_missing_uses_microsd_fallback_without_crashing(tmp_path):
    primary = tmp_path / "missing" / "lkg.json"
    fallback = tmp_path / "fallback.json"
    fallback.write_text(json.dumps(payload("fallback")), encoding="utf-8")
    store = LastKnownGoodStore(primary, fallback)

    status = store.status()
    assert store.read()["events"][0]["title"] == "fallback"
    assert status.using_fallback is True
    assert store.write_if_changed(payload("new"), cycle_id=1) is False
