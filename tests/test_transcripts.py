"""Reading slots out of agent transcripts, using small hand-written files."""

from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import date
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


def test_roots_default_to_the_home_directory(monkeypatch):
    monkeypatch.delenv("DESKHOURS_CURSOR_ROOT", raising=False)
    monkeypatch.delenv("DESKHOURS_CLAUDE_ROOT", raising=False)
    monkeypatch.delenv("DESKHOURS_CODEX_ROOTS", raising=False)
    roots = transcripts.all_roots()
    assert roots["cursor"] == (Path.home() / ".cursor" / "projects",)
    assert roots["claude"] == (Path.home() / ".claude" / "projects",)
    assert len(roots["codex"]) == 2


def test_environment_moves_a_relocated_harness(monkeypatch, tmp_path):
    """A harness pointed somewhere else is the case a disk search is often reached for."""
    monkeypatch.setenv("DESKHOURS_CLAUDE_ROOT", str(tmp_path / "elsewhere"))
    monkeypatch.setenv(
        "DESKHOURS_CODEX_ROOTS", os.pathsep.join([str(tmp_path / "live"), str(tmp_path / "old")])
    )
    assert transcripts.claude_roots() == (tmp_path / "elsewhere",)
    assert transcripts.codex_roots() == (tmp_path / "live", tmp_path / "old")


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


def test_unknown_harness_is_rejected():
    with pytest.raises(ValueError, match="unknown harness"):
        transcripts.collect_all(harnesses=["cursor", "aider"])
