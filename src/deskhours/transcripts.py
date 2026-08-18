"""Read active slots from AI coding-agent transcripts.

Three agent harnesses keep a session log on disk, each with its own layout:

  cursor  ~/.cursor/projects/<slug>/agent-transcripts/<uuid>/<uuid>.jsonl
          Human prompts carry a "<timestamp>Weekday, Mon DD, YYYY, H:MM AM/PM (UTC+N)"
          wrapper, which is already local time and needs no conversion.

  claude  ~/.claude/projects/<slug>/<uuid>.jsonl
          Every line carries "timestamp" in UTC. Only real human turns count, because the
          file also holds assistant turns, tool results and background monitor events.

  codex   ~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl and ~/.codex/archived_sessions/
          Human prompts are event_msg lines whose payload type is "user_message".
          Codex files sessions by date rather than by project, so the project a session
          belongs to is only available from the cwd in its session_meta line.

Counting rule: a slot counts as active when it holds at least one HUMAN prompt. Counting
agent-side lines instead would turn a long unattended run or an overnight monitor into
active time.

Projects are discovered, not configured: whatever directories a harness has created are
read. Only the harness root itself is fixed, and an environment variable moves it when a
harness has been relocated. Searching the disk for transcripts instead would be worse than
it sounds — a sandboxed agent session can hold a nested copy of the very same layout, and
counting that would credit an agent's own turns as time a person spent working.
"""

from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

from deskhours.config import SLOT_MINUTES
from deskhours.core import Slot, slot_at

ALL_HARNESSES = ("cursor", "claude", "codex")


def _from_env(name: str, *default: Path) -> tuple[Path, ...]:
    """Read the roots for one harness, allowing an override in the environment.

    Several paths are joined the way the platform joins PATH, so one variable can carry
    the live and archived directories a harness keeps apart.
    """
    raw = os.environ.get(name)
    if not raw:
        return default
    return tuple(Path(part).expanduser() for part in raw.split(os.pathsep) if part)


def cursor_roots() -> tuple[Path, ...]:
    return _from_env("DESKHOURS_CURSOR_ROOT", Path.home() / ".cursor" / "projects")


def claude_roots() -> tuple[Path, ...]:
    return _from_env("DESKHOURS_CLAUDE_ROOT", Path.home() / ".claude" / "projects")


def codex_roots() -> tuple[Path, ...]:
    return _from_env(
        "DESKHOURS_CODEX_ROOTS",
        Path.home() / ".codex" / "sessions",
        Path.home() / ".codex" / "archived_sessions",
    )


def all_roots() -> dict[str, tuple[Path, ...]]:
    return {
        "cursor": cursor_roots(),
        "claude": claude_roots(),
        "codex": codex_roots(),
    }

_CURSOR_TS = re.compile(
    r"<timestamp>[A-Za-z]+, ([A-Za-z]{3,9}) (\d{1,2}), (\d{4}), (\d{1,2}):(\d{2}) ([AP]M) \(UTC"
)
_MONTHS = {
    name: number
    for number, name in enumerate(
        ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1
    )
}
_MONTHS.update(
    {
        name: number
        for number, name in enumerate(
            [
                "January",
                "February",
                "March",
                "April",
                "May",
                "June",
                "July",
                "August",
                "September",
                "October",
                "November",
                "December",
            ],
            1,
        )
    }
)

# Turns Claude Code files as "user" that nobody typed.
_CLAUDE_SYNTHETIC_PREFIXES = (
    "Caveat:",
    "<task-notification",
    "<local-command-stdout",
    "<command-name>",
    "<command-message>",
    "<system-reminder",
)

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalise(text: str) -> str:
    """Fold a path or a project slug into one comparable form.

    A project is spelled three ways across the harnesses: with spaces in a Codex cwd, and
    with separators already collapsed in a Cursor or Claude directory slug. Folding every
    run of non-alphanumerics to a single dash makes one filter string match all three.
    """
    return _NON_ALNUM.sub("-", text.lower())


def _matches_project(candidate: str, project: str | None) -> bool:
    if not project:
        return True
    return normalise(project).strip("-") in normalise(candidate)


def _to_local(timestamp: object) -> datetime | None:
    """UTC timestamp string to local time, using the offset in force at that instant."""
    if not isinstance(timestamp, str):
        return None
    try:
        return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).astimezone()
    except ValueError:
        return None


def _read_lines(path: Path) -> list[str]:
    try:
        with path.open(encoding="utf-8", errors="ignore") as handle:
            return handle.readlines()
    except OSError:
        return []


def _loads(line: str) -> dict | None:
    try:
        obj = json.loads(line)
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None


def _add(days: dict, moment: datetime, slot_minutes: int) -> None:
    days[moment.date()].add(slot_at(moment, slot_minutes))


def claude_human_text(obj: dict) -> str | None:
    """The text of a turn a person actually typed, or None.

    Claude Code files tool results, injected system reminders, background task
    notifications and slash-command output under the same "user" type. Those are not
    contact time, and overnight monitor events would otherwise read as active hours.
    """
    if obj.get("type") != "user" or obj.get("isMeta"):
        return None
    content = obj.get("message", {}).get("content")
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        text = "\n".join(
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        )
    else:
        return None
    text = re.sub(r"<system-reminder>.*?</system-reminder>", "", text, flags=re.DOTALL).strip()
    if not text:
        return None
    if text.startswith(_CLAUDE_SYNTHETIC_PREFIXES):
        return None
    return text


def codex_session_meta(lines: Iterable[str]) -> tuple[str | None, bool]:
    """Return the session cwd and whether the session belongs to a subagent."""
    cwd: str | None = None
    subagent = False
    for line in lines:
        obj = _loads(line)
        if obj is None or obj.get("type") != "session_meta":
            continue
        payload = obj.get("payload") or {}
        if cwd is None:
            cwd = payload.get("cwd")
        source = payload.get("source")
        if isinstance(source, dict) and source.get("subagent") is not None:
            subagent = True
        if payload.get("parent_thread_id"):
            subagent = True
    return cwd, subagent


def _files(roots: Iterable[Path | str] | None, fallback: Iterable[Path], pattern: str) -> list[Path]:
    """Every file matching the pattern under any root, de-duplicated and ordered.

    A root that does not exist yields nothing rather than failing, which is what makes a
    machine with only one of the three harnesses installed work without configuration.
    """
    found: set[Path] = set()
    for root in roots or fallback:
        found.update(Path(root).glob(pattern))
    return sorted(found)


def collect_cursor(days: dict, slot_minutes: int, roots: Iterable[Path | str] | None = None,
                   project: str | None = None) -> int:
    """Cursor: pull the local-time wrapper straight out of each transcript."""
    prompts = 0
    for path in _files(roots, cursor_roots(), "*/agent-transcripts/*/*.jsonl"):
        if not _matches_project(path.parts[-4], project):
            continue
        try:
            data = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for month_name, day, year, hour, minute, meridiem in _CURSOR_TS.findall(data):
            month = _MONTHS.get(month_name)
            if not month:
                continue
            hour24 = int(hour) % 12 + (12 if meridiem == "PM" else 0)
            _add(days, datetime(int(year), month, int(day), hour24, int(minute)), slot_minutes)
            prompts += 1
    return prompts


def collect_claude(days: dict, slot_minutes: int, roots: Iterable[Path | str] | None = None,
                   project: str | None = None) -> int:
    """Claude Code: per-line UTC timestamps, human turns only."""
    prompts = 0
    for path in _files(roots, claude_roots(), "*/*.jsonl"):
        if not _matches_project(path.parent.name, project):
            continue
        for line in _read_lines(path):
            obj = _loads(line)
            if obj is None or claude_human_text(obj) is None:
                continue
            moment = _to_local(obj.get("timestamp"))
            if moment:
                _add(days, moment, slot_minutes)
                prompts += 1
    return prompts


def collect_codex(days: dict, slot_minutes: int, roots: Iterable[Path | str] | None = None,
                  project: str | None = None) -> int:
    """Codex: top-level user_message events, scoped by the session cwd."""
    prompts = 0
    files = _files(roots, codex_roots(), "**/rollout-*.jsonl")
    for path in files:
        lines = _read_lines(path)
        cwd, subagent = codex_session_meta(lines)
        if subagent:
            continue
        if cwd is not None and not _matches_project(cwd, project):
            continue
        for line in lines:
            obj = _loads(line)
            if obj is None or obj.get("type") != "event_msg":
                continue
            payload = obj.get("payload") or {}
            if payload.get("type") != "user_message":
                continue
            moment = _to_local(obj.get("timestamp"))
            if moment:
                _add(days, moment, slot_minutes)
                prompts += 1
    return prompts


def collect_all(
    slot_minutes: int = SLOT_MINUTES,
    harnesses: Iterable[str] = ALL_HARNESSES,
    project: str | None = None,
) -> tuple[dict, dict[str, tuple[int, int]]]:
    """Merge every requested harness into one day-to-slot-set map.

    The second return value maps a harness to its (prompt count, day count) so a harness
    that has gone silent is visible instead of quietly dropping out of the total.
    """
    days: dict = defaultdict(set)
    per_harness: dict[str, tuple[int, int]] = {}
    readers = {"cursor": collect_cursor, "claude": collect_claude, "codex": collect_codex}
    for name in harnesses:
        try:
            reader = readers[name]
        except KeyError:
            raise ValueError(f"unknown harness: {name}") from None
        own: dict = defaultdict(set)
        prompts = reader(own, slot_minutes, None, project)
        per_harness[name] = (prompts, len(own))
        for day, slots in own.items():
            days[day] |= slots
    return days, per_harness


def slots_for_day(
    day: date | None = None,
    slot_minutes: int = SLOT_MINUTES,
    harnesses: Iterable[str] = ALL_HARNESSES,
    project: str | None = None,
) -> tuple[set[Slot], dict[str, tuple[int, int]]]:
    """Active slots for one local date, plus the per-harness prompt counts behind them."""
    days, per_harness = collect_all(slot_minutes, harnesses, project)
    return days.get(day or date.today(), set()), per_harness
