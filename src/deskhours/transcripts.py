"""Read active slots from AI coding-agent transcripts.

Three agent harnesses keep a session log on disk, each with its own layout:

  cursor  ~/.cursor/projects/<slug>/agent-transcripts/<uuid>/<uuid>.jsonl
          Human prompts carry a "<timestamp>Weekday, Mon DD, YYYY, H:MM AM/PM (UTC+N)"
          wrapper, which is already local time and needs no conversion.

  claude  ~/.claude/projects/<slug>/<uuid>.jsonl
          Every line carries "timestamp" in UTC. Only real human turns count, because the
          file also holds assistant turns, tool results and background monitor events.

  codex   ~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl and ~/.codex/archived_sessions/
          Human prompts are event_msg lines: a completed "UserMessage" item in the current
          format, a "user_message" event in the older one, and sometimes both for one prompt.
          Codex files sessions by date rather than by project, so the project a session
          belongs to is only available from the cwd in its session_meta line.

Counting rule: a slot counts as active when it holds at least one HUMAN prompt. Counting
agent-side lines instead would turn a long unattended run or an overnight monitor into
active time.

Nothing is configured by hand. Projects come from whatever directories a harness has
created, and the harness root itself is looked for under the few places the three operating
systems keep user data. Searching the whole disk instead answers the same question
thousands of times slower, needs access to every file on macOS, and is not even safe: a
sandboxed agent session can hold a nested copy of the very same layout, so counting what
turns up would credit an agent's own turns as time a person spent working.
"""

from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from collections.abc import Iterable
from datetime import date, datetime, timedelta
from pathlib import Path

from deskhours.config import SLOT_MINUTES
from deskhours.core import Slot, slot_at

ALL_HARNESSES = ("cursor", "claude", "codex")

_LAYOUT = {
    "cursor": (".cursor/projects",),
    "claude": (".claude/projects",),
    "codex": (".codex/sessions", ".codex/archived_sessions"),
}
ENV_OVERRIDES = {
    "cursor": "DESKHOURS_CURSOR_ROOT",
    "claude": "DESKHOURS_CLAUDE_ROOT",
    "codex": "DESKHOURS_CODEX_ROOTS",
}
_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def candidate_parents() -> tuple[Path, ...]:
    """The few places a harness keeps user data, across the three operating systems.

    Checking a short list costs a handful of directory tests, which is cheap enough to
    repeat on every poll. Walking the disk to answer the same question is thousands of
    times slower and, on macOS, needs access to the whole disk to even try.
    """
    home = Path.home()
    parents = [
        home,
        home / "Library" / "Application Support",
        home / ".config",
        home / ".local" / "share",
    ]
    for variable in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "APPDATA", "LOCALAPPDATA"):
        value = os.environ.get(variable)
        if value:
            parents.append(Path(value))
    return tuple(dict.fromkeys(parents))


def harness_roots(harness: str) -> tuple[Path, ...]:
    """Where this harness keeps its sessions on this machine.

    An override in the environment wins outright. Otherwise the layout is looked for under
    each candidate parent, so nothing needs configuring after a normal install. When the
    harness is absent the conventional path is still returned, so a report can name what
    it looked for instead of staying silent.
    """
    if harness not in _LAYOUT:
        raise ValueError(f"unknown harness: {harness}")

    override = os.environ.get(ENV_OVERRIDES[harness])
    if override:
        return tuple(Path(part).expanduser() for part in override.split(os.pathsep) if part)

    found: list[Path] = []
    for parent in candidate_parents():
        for relative in _LAYOUT[harness]:
            candidate = parent.joinpath(*relative.split("/"))
            if candidate.is_dir() and candidate not in found:
                found.append(candidate)
    if found:
        return tuple(found)
    return tuple(Path.home().joinpath(*r.split("/")) for r in _LAYOUT[harness])


def all_roots() -> dict[str, tuple[Path, ...]]:
    return {harness: harness_roots(harness) for harness in ALL_HARNESSES}


def scan(directory: Path | str) -> dict[str, list[Path]]:
    """Search a directory tree for harness layouts, for the rare relocated install.

    Two kinds of match are thrown away. A copy sitting under a directory named like a
    session id belongs to a sandboxed agent run: it has the same layout and the same file
    names, and counting it would read an agent's own turns as time a person worked. A
    match nested inside another match is the same story one level down.
    """
    directory = Path(directory).expanduser()
    marker_owner = {
        tuple(relative.split("/")): harness
        for harness, relatives in _LAYOUT.items()
        for relative in relatives
    }
    marker_names = {marker[0] for marker in marker_owner}
    hits: dict[str, list[Path]] = {harness: [] for harness in ALL_HARNESSES}
    for current, subdirs, _ in os.walk(directory, onerror=lambda _: None):
        path = Path(current)
        for marker, harness in marker_owner.items():
            if path.parts[-len(marker) :] != marker:
                continue
            above = str(path.parents[len(marker) - 1])
            if not _UUID.search(above) and not any(name in above for name in marker_names):
                hits[harness].append(path)
            subdirs[:] = []
    return hits


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


# Codex records inherited subagent history and question-widget answers as user
# input even though nobody typed them as a new prompt.
_CODEX_SYNTHETIC_PREFIXES = (
    "The following is the Codex agent history",
    "<send_user_message_question_reply>",
    "<heartbeat>",
    "<external_codex_apps_open_page>",
    "<environment_context>",
    "# AGENTS.md instructions",
)
_CODEX_BROWSER_CONTEXT = re.compile(
    r"<in-app-browser-context.*?</in-app-browser-context>", re.DOTALL
)


def codex_prompt_text(obj: dict) -> str | None:
    """The text of a Codex prompt a person typed, or None.

    The in-app browser attaches its tab state to a typed prompt. Remove that
    block and keep the actual prompt.
    """
    if obj.get("type") != "event_msg":
        return None
    payload = obj.get("payload") or {}
    item = payload.get("item") or {}
    if payload.get("type") == "user_message":
        text = payload.get("message")
    elif payload.get("type") == "item_completed" and item.get("type") == "UserMessage":
        text = "\n".join(
            part.get("text", "") for part in item.get("content") or [] if isinstance(part, dict)
        )
    else:
        return None
    if not isinstance(text, str):
        return None
    text = _CODEX_BROWSER_CONTEXT.sub("", text).strip()
    if not text or text.startswith(_CODEX_SYNTHETIC_PREFIXES):
        return None
    return text


def codex_prompts(lines: Iterable[str]) -> list[tuple[str, str]]:
    """Return each typed prompt once, even when both event formats record it."""
    seen: set[tuple[str, str]] = set()
    prompts = []
    for line in lines:
        obj = _loads(line)
        if obj is None:
            continue
        text = codex_prompt_text(obj)
        timestamp = obj.get("timestamp")
        if text is None or not isinstance(timestamp, str):
            continue
        # Both formats are written milliseconds apart; minute and text identify
        # the same prompt.
        key = (timestamp[:16], " ".join(text.split()))
        if key in seen:
            continue
        seen.add(key)
        prompts.append((timestamp, text))
    return prompts


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


def _files(
    roots: Iterable[Path | str] | None,
    fallback: Iterable[Path],
    pattern: str,
    modified_after: datetime | None = None,
) -> list[Path]:
    """Every file matching the pattern under any root, de-duplicated and ordered.

    A root that does not exist yields nothing rather than failing, which is what makes a
    machine with only one of the three harnesses installed work without configuration.

    `modified_after` skips logs that were last written before that moment. Sessions are
    appended to as they happen, so such a file cannot hold a prompt from a later day, and
    a count for one day does not have to read years of history to find that out.
    """
    cutoff = modified_after.timestamp() if modified_after else None
    found: set[Path] = set()
    for root in roots or fallback:
        for path in Path(root).glob(pattern):
            if cutoff is not None:
                try:
                    if path.stat().st_mtime < cutoff:
                        continue
                except OSError:
                    continue
            found.add(path)
    return sorted(found)


def collect_cursor(
    days: dict,
    slot_minutes: int,
    roots: Iterable[Path | str] | None = None,
    project: str | None = None,
    *,
    modified_after: datetime | None = None,
) -> int:
    """Cursor: pull the local-time wrapper straight out of each transcript."""
    prompts = 0
    for path in _files(
        roots, harness_roots("cursor"), "*/agent-transcripts/*/*.jsonl", modified_after
    ):
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


def collect_claude(
    days: dict,
    slot_minutes: int,
    roots: Iterable[Path | str] | None = None,
    project: str | None = None,
    *,
    modified_after: datetime | None = None,
) -> int:
    """Claude Code: per-line UTC timestamps, human turns only."""
    prompts = 0
    for path in _files(roots, harness_roots("claude"), "*/*.jsonl", modified_after):
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


def collect_codex(
    days: dict,
    slot_minutes: int,
    roots: Iterable[Path | str] | None = None,
    project: str | None = None,
    *,
    modified_after: datetime | None = None,
) -> int:
    """Codex: typed prompts of top-level sessions, scoped by the session cwd."""
    prompts = 0
    files = _files(roots, harness_roots("codex"), "**/rollout-*.jsonl", modified_after)
    for path in files:
        lines = _read_lines(path)
        cwd, subagent = codex_session_meta(lines)
        if subagent:
            continue
        if cwd is not None and not _matches_project(cwd, project):
            continue
        for timestamp, _ in codex_prompts(lines):
            moment = _to_local(timestamp)
            if moment:
                _add(days, moment, slot_minutes)
                prompts += 1
    return prompts


def collect_all(
    slot_minutes: int = SLOT_MINUTES,
    harnesses: Iterable[str] = ALL_HARNESSES,
    project: str | None = None,
    modified_after: datetime | None = None,
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
        prompts = reader(own, slot_minutes, None, project, modified_after=modified_after)
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
    """Active slots for one local date, plus the per-harness prompt counts behind them.

    Only logs written on or after that date can hold its prompts, so the rest are skipped.
    Without that, a poller running every few minutes would re-read every session ever
    recorded, and the work would grow with the whole history instead of with the day. The
    extra day of margin covers a machine whose clock or timezone disagrees slightly.
    """
    day = day or date.today()
    cutoff = datetime.combine(day, datetime.min.time()) - timedelta(days=1)
    days, per_harness = collect_all(slot_minutes, harnesses, project, modified_after=cutoff)
    return days.get(day, set()), per_harness
