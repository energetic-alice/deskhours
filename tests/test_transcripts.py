"""Reading slots out of agent transcripts, using small hand-written files."""

from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from deskhours import transcripts

SLOT = 30


def days() -> dict:
    return defaultdict(set)


def write_lines(path, objects) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(o) for o in objects) + "\n", encoding="utf-8")


def test_normalise_folds_every_spelling_of_one_project():
    spellings = [
        "/home/dev/Projects/My API",
        "Users-dev-Projects-My-API",
        "My_API",
    ]
    assert all("my-api" in transcripts.normalise(s) for s in spellings)


def test_cursor_reads_the_local_time_wrapper(tmp_path):
    path = tmp_path / "my-project" / "agent-transcripts" / "abc" / "abc.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text(
        "<timestamp>Tuesday, Aug 18, 2026, 2:04 PM (UTC+1)</timestamp>\n"
        "<timestamp>Tuesday, Aug 18, 2026, 2:29 PM (UTC+1)</timestamp>\n"
        "<timestamp>Tuesday, August 18, 2026, 9:05 AM (UTC+1)</timestamp>\n",
        encoding="utf-8",
    )
    found = days()
    prompts = transcripts.collect_cursor(found, SLOT, roots=[tmp_path])
    assert prompts == 3
    assert found[date(2026, 8, 18)] == {(14, 0), (9, 0)}


def test_cursor_honours_the_project_filter(tmp_path):
    for project in ("my-api", "other-repo"):
        path = tmp_path / project / "agent-transcripts" / "x" / "x.jsonl"
        path.parent.mkdir(parents=True)
        path.write_text(
            "<timestamp>Tuesday, Aug 18, 2026, 2:04 PM (UTC+1)</timestamp>\n", encoding="utf-8"
        )
    assert transcripts.collect_cursor(days(), SLOT, roots=[tmp_path]) == 2
    assert transcripts.collect_cursor(days(), SLOT, roots=[tmp_path], project="My API") == 1


@pytest.mark.parametrize(
    "line",
    [
        {"type": "assistant", "timestamp": "2026-08-18T13:04:00Z", "message": {"content": "hi"}},
        {
            "type": "user",
            "isMeta": True,
            "timestamp": "2026-08-18T13:04:00Z",
            "message": {"content": "meta"},
        },
        {
            "type": "user",
            "timestamp": "2026-08-18T13:04:00Z",
            "message": {"content": "<system-reminder>watch out</system-reminder>"},
        },
        {
            "type": "user",
            "timestamp": "2026-08-18T13:04:00Z",
            "message": {"content": "Caveat: this was injected"},
        },
        {
            "type": "user",
            "timestamp": "2026-08-18T13:04:00Z",
            "message": {"content": [{"type": "tool_result", "content": "output"}]},
        },
    ],
)
def test_claude_ignores_turns_nobody_typed(tmp_path, line):
    write_lines(tmp_path / "proj" / "s.jsonl", [line])
    assert transcripts.collect_claude(days(), SLOT, roots=[tmp_path]) == 0


def test_claude_counts_real_prompts_once_per_slot(tmp_path):
    write_lines(
        tmp_path / "proj" / "s.jsonl",
        [
            {
                "type": "user",
                "timestamp": "2026-08-18T13:04:00Z",
                "message": {"content": "fix the gate"},
            },
            {
                "type": "user",
                "timestamp": "2026-08-18T13:06:00Z",
                "message": {"content": [{"type": "text", "text": "and rerun it"}]},
            },
        ],
    )
    found = days()
    assert transcripts.collect_claude(found, SLOT, roots=[tmp_path]) == 2
    assert sum(len(slots) for slots in found.values()) == 1


def test_codex_skips_subagent_sessions_and_scopes_by_cwd(tmp_path):
    prompt = {
        "type": "event_msg",
        "timestamp": "2026-08-18T13:04:00Z",
        "payload": {"type": "user_message", "message": "go"},
    }
    cwd = "/home/dev/Projects/web-api"
    write_lines(
        tmp_path / "2026" / "08" / "18" / "rollout-main.jsonl",
        [{"type": "session_meta", "payload": {"cwd": cwd}}, prompt],
    )
    write_lines(
        tmp_path / "2026" / "08" / "18" / "rollout-sub.jsonl",
        [
            {"type": "session_meta", "payload": {"cwd": cwd, "parent_thread_id": "t1"}},
            prompt,
        ],
    )
    assert transcripts.collect_codex(days(), SLOT, roots=[tmp_path]) == 1
    assert transcripts.collect_codex(days(), SLOT, roots=[tmp_path], project="web api") == 1
    assert transcripts.collect_codex(days(), SLOT, roots=[tmp_path], project="mobile") == 0


def test_roots_may_be_plain_strings(tmp_path):
    """Callers outside the package pass paths as strings."""
    write_lines(
        tmp_path / "proj" / "s.jsonl",
        [
            {
                "type": "user",
                "timestamp": "2026-08-18T13:04:00Z",
                "message": {"content": "typed by a person"},
            }
        ],
    )
    assert transcripts.collect_claude(days(), SLOT, roots=[str(tmp_path)]) == 1
    assert transcripts.collect_codex(days(), SLOT, roots=[str(tmp_path)]) == 0
    assert transcripts.collect_cursor(days(), SLOT, roots=[str(tmp_path)]) == 0


def test_a_machine_without_that_harness_reports_zero(tmp_path):
    """No installed harness, no crash: the count just has nothing to add."""
    missing = tmp_path / "nothing here"
    assert transcripts.collect_cursor(days(), SLOT, roots=[missing]) == 0
    assert transcripts.collect_claude(days(), SLOT, roots=[missing]) == 0
    assert transcripts.collect_codex(days(), SLOT, roots=[missing]) == 0


@pytest.fixture
def fake_home(monkeypatch, tmp_path):
    """A machine of our own, with no overrides set."""
    for variable in transcripts.ENV_OVERRIDES.values():
        monkeypatch.delenv(variable, raising=False)
    for variable in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "APPDATA", "LOCALAPPDATA"):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    return tmp_path


def test_an_installed_harness_is_found_without_configuration(fake_home):
    (fake_home / ".claude" / "projects").mkdir(parents=True)
    (fake_home / ".codex" / "sessions").mkdir(parents=True)
    assert transcripts.harness_roots("claude") == (fake_home / ".claude" / "projects",)
    assert transcripts.harness_roots("codex") == (fake_home / ".codex" / "sessions",)


def test_a_harness_under_the_application_support_folder_is_found(fake_home):
    """Same layout, different parent: found by looking, not by hardcoding one path."""
    moved = fake_home / "Library" / "Application Support" / ".cursor" / "projects"
    moved.mkdir(parents=True)
    assert transcripts.harness_roots("cursor") == (moved,)


def test_a_missing_harness_still_names_what_was_looked_for(fake_home):
    """A report that says nothing is worse than one that says where it looked."""
    assert transcripts.harness_roots("claude") == (fake_home / ".claude" / "projects",)


def test_an_override_wins_over_what_was_found(fake_home):
    (fake_home / ".claude" / "projects").mkdir(parents=True)
    os.environ["DESKHOURS_CLAUDE_ROOT"] = str(fake_home / "elsewhere")
    try:
        assert transcripts.harness_roots("claude") == (fake_home / "elsewhere",)
    finally:
        del os.environ["DESKHOURS_CLAUDE_ROOT"]


def test_an_override_carries_several_paths(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "DESKHOURS_CODEX_ROOTS", os.pathsep.join([str(tmp_path / "live"), str(tmp_path / "old")])
    )
    assert transcripts.harness_roots("codex") == (tmp_path / "live", tmp_path / "old")


def test_scan_finds_a_relocated_harness(tmp_path):
    real = tmp_path / "Volumes" / "work" / ".claude" / "projects"
    real.mkdir(parents=True)
    assert transcripts.scan(tmp_path)["claude"] == [real]


def test_scan_leaves_out_a_sandboxed_agent_copy(tmp_path):
    """The nested copy has the same layout; only its ancestors give it away."""
    real = tmp_path / ".claude" / "projects"
    real.mkdir(parents=True)
    sandbox = (
        tmp_path
        / "Application Support"
        / "local-agent-mode-sessions"
        / "c1f81119-eb22-4720-aede-b129cea3724a"
        / "local_17b9019f-b2e3-4470-98b1-0339ddd23e28"
        / ".claude"
        / "projects"
    )
    sandbox.mkdir(parents=True)
    found = transcripts.scan(tmp_path)["claude"]
    assert found == [real]
    assert sandbox not in found


def test_scan_leaves_out_a_copy_inside_another_harness(tmp_path):
    real = tmp_path / ".cursor" / "projects"
    real.mkdir(parents=True)
    (real / "some-project" / ".cursor" / "projects").mkdir(parents=True)
    assert transcripts.scan(tmp_path)["cursor"] == [real]


def test_relocated_root_is_actually_read(monkeypatch, tmp_path):
    monkeypatch.setenv("DESKHOURS_CLAUDE_ROOT", str(tmp_path))
    write_lines(
        tmp_path / "proj" / "s.jsonl",
        [
            {
                "type": "user",
                "timestamp": "2026-08-18T13:04:00Z",
                "message": {"content": "typed by a person"},
            }
        ],
    )
    _, per_harness = transcripts.collect_all(SLOT, harnesses=["claude"])
    assert per_harness["claude"][0] == 1


def test_one_day_does_not_read_logs_written_before_it(monkeypatch, tmp_path):
    """The poller runs every few minutes; without this it re-reads the whole history."""
    monkeypatch.setenv("DESKHOURS_CLAUDE_ROOT", str(tmp_path))
    today = date.today()
    prompt = {
        "type": "user",
        "timestamp": f"{today.isoformat()}T09:04:00Z",
        "message": {"content": "typed by a person"},
    }
    fresh = tmp_path / "proj" / "fresh.jsonl"
    stale = tmp_path / "proj" / "stale.jsonl"
    write_lines(fresh, [prompt])
    write_lines(stale, [prompt])
    long_ago = (datetime.now() - timedelta(days=10)).timestamp()
    os.utime(stale, (long_ago, long_ago))

    _, per_harness = transcripts.slots_for_day(today, harnesses=["claude"])

    assert per_harness["claude"][0] == 1, "the stale file was read even though it cannot matter"


def test_a_log_touched_today_is_read(monkeypatch, tmp_path):
    monkeypatch.setenv("DESKHOURS_CLAUDE_ROOT", str(tmp_path))
    today = date.today()
    write_lines(
        tmp_path / "proj" / "s.jsonl",
        [
            {
                "type": "user",
                "timestamp": f"{today.isoformat()}T09:04:00Z",
                "message": {"content": "typed by a person"},
            }
        ],
    )
    slots, _ = transcripts.slots_for_day(today, slot_minutes=30, harnesses=["claude"])
    assert len(slots) == 1


def test_unknown_harness_is_rejected():
    with pytest.raises(ValueError, match="unknown harness"):
        transcripts.collect_all(harnesses=["cursor", "aider"])
