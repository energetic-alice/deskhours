"""Choosing a signal, and what each signal is allowed to claim."""

from __future__ import annotations

from datetime import datetime

import pytest

from deskhours import platform, sources, transcripts

NOW = datetime(2026, 8, 18, 14, 4)
SLOT = 30


def test_input_reports_only_the_present_moment(monkeypatch):
    monkeypatch.setattr(platform, "idle_seconds", lambda: 12.0)
    reading = sources.read("input", now=NOW, idle_threshold=300)
    assert reading.active is True
    assert reading.slots is None
    assert "idle=12s" in reading.detail


def test_input_goes_quiet_past_the_idle_threshold(monkeypatch):
    monkeypatch.setattr(platform, "idle_seconds", lambda: 900.0)
    assert sources.read("input", now=NOW, idle_threshold=300).active is False


def test_agents_rebuilds_the_whole_day(monkeypatch):
    monkeypatch.setattr(
        transcripts,
        "slots_for_day",
        lambda *a, **k: ({(9, 0), (14, 0)}, {"cursor": (7, 1), "claude": (0, 0)}),
    )
    reading = sources.read("agents", now=NOW, slot_minutes=SLOT)
    assert reading.slots == {(9, 0), (14, 0)}
    assert reading.active is True
    assert "cursor=7" in reading.detail and "claude=0" in reading.detail


def test_agents_is_inactive_when_the_current_slot_holds_no_prompt(monkeypatch):
    monkeypatch.setattr(
        transcripts, "slots_for_day", lambda *a, **k: ({(9, 0)}, {"cursor": (1, 1)})
    )
    reading = sources.read("agents", now=NOW, slot_minutes=SLOT)
    assert reading.active is False
    assert reading.slots == {(9, 0)}


def test_agents_never_touches_the_idle_backend(monkeypatch):
    """The agent count has to work where no idle backend exists."""

    def refuse():
        raise platform.UnsupportedPlatformError("no backend here")

    monkeypatch.setattr(platform, "idle_seconds", refuse)
    monkeypatch.setattr(transcripts, "slots_for_day", lambda *a, **k: (set(), {}))
    assert sources.read("agents", now=NOW).active is False


def test_unknown_source_is_rejected():
    with pytest.raises(ValueError, match="unknown source"):
        sources.read("mailbox", now=NOW)
