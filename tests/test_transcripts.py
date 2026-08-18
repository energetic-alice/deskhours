"""Reading slots out of agent transcripts, using small hand-written files."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import date

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
        "/Users/alisa/Documents/Claude/Projects/DevOps Assistant",
        "Users-alisa-Documents-Claude-Projects-DevOps-Assistant",
        "DevOps_Assistant",
    ]
    assert all("devops-assistant" in transcripts.normalise(s) for s in spellings)


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
    prompts = transcripts.collect_cursor(found, SLOT, root=tmp_path)
    assert prompts == 3
    assert found[date(2026, 8, 18)] == {(14, 0), (9, 0)}


def test_cursor_honours_the_project_filter(tmp_path):
    for project in ("devops-assistant", "other-repo"):
        path = tmp_path / project / "agent-transcripts" / "x" / "x.jsonl"
        path.parent.mkdir(parents=True)
        path.write_text(
            "<timestamp>Tuesday, Aug 18, 2026, 2:04 PM (UTC+1)</timestamp>\n", encoding="utf-8"
        )
    assert transcripts.collect_cursor(days(), SLOT, root=tmp_path) == 2
    assert transcripts.collect_cursor(days(), SLOT, root=tmp_path, project="DevOps Assistant") == 1


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
    assert transcripts.collect_claude(days(), SLOT, root=tmp_path) == 0


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
    assert transcripts.collect_claude(found, SLOT, root=tmp_path) == 2
    assert sum(len(slots) for slots in found.values()) == 1


def test_codex_skips_subagent_sessions_and_scopes_by_cwd(tmp_path):
    prompt = {
        "type": "event_msg",
        "timestamp": "2026-08-18T13:04:00Z",
        "payload": {"type": "user_message", "message": "go"},
    }
    cwd = "/Users/a/Projects/candy-infrastructure"
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
    assert transcripts.collect_codex(days(), SLOT, roots=[tmp_path], project="candy-infra") == 1
    assert transcripts.collect_codex(days(), SLOT, roots=[tmp_path], project="argo-cd") == 0


def test_unknown_harness_is_rejected():
    with pytest.raises(ValueError, match="unknown harness"):
        transcripts.collect_all(harnesses=["cursor", "aider"])
