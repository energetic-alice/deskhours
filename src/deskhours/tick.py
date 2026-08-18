"""One poll cycle: read the chosen signal → update slots → maybe remind."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from deskhours import platform, sources
from deskhours.config import (
    DEFAULT_SOURCE,
    IDLE_THRESHOLD_SEC,
    NOTIFY_MESSAGES,
    NOTIFY_THRESHOLD_H,
    NOTIFY_TITLE,
    SLOT_MINUTES,
)
from deskhours.core import DayState, should_notify
from deskhours.state import load_state, save_state


@dataclass(frozen=True)
class TickResult:
    hours: float
    active: bool
    notified: bool
    clock_hours: list[int]
    source: str
    detail: str
    state: DayState


def run_tick(
    *,
    source: str = DEFAULT_SOURCE,
    project: str | None = None,
    idle_threshold: float = IDLE_THRESHOLD_SEC,
    slot_minutes: int = SLOT_MINUTES,
    notify_threshold: float = NOTIFY_THRESHOLD_H,
    dry_run: bool = False,
    dialog: bool = False,
    now: datetime | None = None,
    state_path: Path | None = None,
) -> TickResult:
    now = now or datetime.now()
    reading = sources.read(
        source,
        now=now,
        slot_minutes=slot_minutes,
        idle_threshold=idle_threshold,
        project=project,
    )

    state = load_state(state_path, source)
    if reading.slots is None:
        if reading.active:
            state.mark(now, slot_minutes)
    else:
        state.slots = set(reading.slots)

    hours = state.hours(slot_minutes)
    notified = False

    if not dry_run:
        save_state(state, state_path, source)
        watermark = should_notify(hours, state.notified_hour, notify_threshold)
        if watermark is not None:
            platform.notify(
                NOTIFY_TITLE,
                NOTIFY_MESSAGES[source].format(hours=hours),
                dialog=dialog,
            )
            state.notified_hour = watermark
            save_state(state, state_path, source)
            notified = True

    return TickResult(
        hours=hours,
        active=reading.active,
        notified=notified,
        clock_hours=state.active_clock_hours(),
        source=source,
        detail=reading.detail,
        state=state,
    )


def format_status(result: TickResult, *, slot_minutes: int, notify_threshold: float) -> str:
    label = "active" if result.active else "idle"
    hours = ", ".join(f"{h:02d}" for h in result.clock_hours) or "-"
    return (
        f"Today: {result.hours:.1f}h  [{result.source}] {result.detail} ({label})  "
        f"slot={slot_minutes}m  threshold={notify_threshold}h  hours=[{hours}]"
    )
