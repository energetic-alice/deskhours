"""How a tick folds a reading into stored state, per source."""

from __future__ import annotations

import json
from datetime import date, datetime

from deskhours import platform, sources, tick
from deskhours.core import DayState
from deskhours.state import default_state_path, save_state

NOW = datetime(2026, 8, 18, 14, 4)
TODAY = date(2026, 8, 18).isoformat()


def seed(path, slots, notified_hour=0):
    save_state(DayState(day=TODAY, slots=set(slots), notified_hour=notified_hour), path)


def reading(monkeypatch, **kwargs):
    monkeypatch.setattr(sources, "read", lambda *a, **k: sources.Reading(**kwargs))


def test_input_adds_the_current_slot_and_keeps_history(monkeypatch, tmp_path):
    state_file = tmp_path / "input.json"
    seed(state_file, [(9, 0)])
    reading(monkeypatch, active=True, detail="idle=3s")

    result = tick.run_tick(source="input", now=NOW, state_path=state_file)

    assert result.state.slots == {(9, 0), (14, 0)}
    assert result.hours == 1.0


def test_input_idle_tick_changes_nothing(monkeypatch, tmp_path):
    state_file = tmp_path / "input.json"
    seed(state_file, [(9, 0)])
    reading(monkeypatch, active=False, detail="idle=900s")

    result = tick.run_tick(source="input", now=NOW, state_path=state_file)

    assert result.state.slots == {(9, 0)}


def test_agents_replaces_the_stored_set(monkeypatch, tmp_path):
    """A slot the transcripts do not back must disappear, so a wrong count can heal."""
    state_file = tmp_path / "agents.json"
    seed(state_file, [(3, 0)])
    reading(monkeypatch, active=True, detail="prompts cursor=4", slots={(9, 0), (14, 0)})

    result = tick.run_tick(source="agents", now=NOW, state_path=state_file)

    assert result.state.slots == {(9, 0), (14, 0)}
    assert json.loads(state_file.read_text())["slots"] == [[9, 0], [14, 0]]


def test_dry_run_writes_nothing(monkeypatch, tmp_path):
    state_file = tmp_path / "agents.json"
    reading(monkeypatch, active=True, detail="prompts cursor=4", slots={(14, 0)})

    tick.run_tick(source="agents", now=NOW, state_path=state_file, dry_run=True)

    assert not state_file.exists()


def test_each_source_gets_its_own_wording(monkeypatch, tmp_path):
    sent = []
    monkeypatch.setattr(
        platform, "notify", lambda title, message, dialog=False: sent.append(message)
    )
    full_day = {(hour, half) for hour in range(9, 18) for half in (0, 1)}

    reading(monkeypatch, active=True, detail="idle=3s")
    tick.run_tick(source="input", now=NOW, state_path=tmp_path / "a.json")
    seed(tmp_path / "a.json", full_day)
    tick.run_tick(source="input", now=NOW, state_path=tmp_path / "a.json")

    reading(monkeypatch, active=True, detail="prompts cursor=4", slots=full_day)
    tick.run_tick(source="agents", now=NOW, state_path=tmp_path / "b.json")

    assert "active at your computer" in sent[0]
    assert "coding agents" in sent[1]


def test_state_files_do_not_collide():
    assert default_state_path("input").name == "state.json"
    assert default_state_path("agents").name == "state-agents.json"
    assert default_state_path("input").parent == default_state_path("agents").parent
