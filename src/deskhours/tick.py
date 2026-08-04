"""One poll cycle: read idle → update slots → maybe remind."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from deskhours import platform
from deskhours.config import (
    IDLE_THRESHOLD_SEC,
    NOTIFY_MESSAGE,
    NOTIFY_THRESHOLD_H,
    NOTIFY_TITLE,
    SLOT_MINUTES,
)
from deskhours.core import DayState, should_notify
from deskhours.state import load_state, save_state


@dataclass(frozen=True)
class TickResult:
    hours: float
    idle_seconds: float
    active: bool
    notified: bool
    clock_hours: list[int]
    state: DayState


def run_tick(
    *,
    idle_threshold: float = IDLE_THRESHOLD_SEC,
    slot_minutes: int = SLOT_MINUTES,
    notify_threshold: float = NOTIFY_THRESHOLD_H,
    dry_run: bool = False,
    dialog: bool = False,
    now: datetime | None = None,
    state_path: Path | None = None,
) -> TickResult:
    now = now or datetime.now()
    idle = platform.idle_seconds()
    active = idle < idle_threshold

    state = load_state(state_path)
    if active:
        state.mark(now, slot_minutes)

    hours = state.hours(slot_minutes)
    notified = False

    if not dry_run:
        save_state(state, state_path)
        watermark = should_notify(hours, state.notified_hour, notify_threshold)
        if watermark is not None:
            platform.notify(
                NOTIFY_TITLE,
                NOTIFY_MESSAGE.format(hours=hours),
                dialog=dialog,
            )
            state.notified_hour = watermark
            save_state(state, state_path)
            notified = True

    return TickResult(
        hours=hours,
        idle_seconds=idle,
        active=active,
        notified=notified,
        clock_hours=state.active_clock_hours(),
        state=state,
    )


def format_status(result: TickResult, *, slot_minutes: int, notify_threshold: float) -> str:
    label = "active" if result.active else "idle"
    hours = ", ".join(f"{h:02d}" for h in result.clock_hours) or "-"
    return (
        f"Today: {result.hours:.1f}h  idle={result.idle_seconds:.0f}s ({label})  "
        f"slot={slot_minutes}m  threshold={notify_threshold}h  hours=[{hours}]"
    )
