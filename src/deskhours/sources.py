"""Where today's active slots come from.

Two signals answer the same question in fundamentally different ways.

`input` can only speak for the present moment: nothing records past idle state, so hours
exist because earlier polls sampled them and saved the result. A missed poll is a lost slot.

`agents` reads a durable log, so it rebuilds the whole day on every call. Hours survive a
missed poll, and the same code can answer for a past day.

That asymmetry is why a reading carries either a complete slot set or nothing at all,
instead of both sources pretending to report the same thing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from deskhours import platform, transcripts
from deskhours.config import ALL_SOURCES, IDLE_THRESHOLD_SEC, SLOT_MINUTES
from deskhours.core import Slot, slot_at


@dataclass(frozen=True)
class Reading:
    """One probe result.

    `slots` holds the complete set for the day when the source can rebuild it, and None
    when the source only knows about right now.
    """

    active: bool
    detail: str
    slots: set[Slot] | None = None


def _read_input(idle_threshold: float) -> Reading:
    idle = platform.idle_seconds()
    return Reading(active=idle < idle_threshold, detail=f"idle={idle:.0f}s")


def _read_agents(now: datetime, slot_minutes: int, project: str | None) -> Reading:
    slots, per_harness = transcripts.slots_for_day(
        now.date(), slot_minutes=slot_minutes, project=project
    )
    counts = " ".join(f"{name}={prompts}" for name, (prompts, _) in per_harness.items())
    return Reading(
        active=slot_at(now, slot_minutes) in slots,
        detail=f"prompts {counts}",
        slots=slots,
    )


def read(
    source: str,
    *,
    now: datetime,
    slot_minutes: int = SLOT_MINUTES,
    idle_threshold: float = IDLE_THRESHOLD_SEC,
    project: str | None = None,
) -> Reading:
    if source == "input":
        return _read_input(idle_threshold)
    if source == "agents":
        return _read_agents(now, slot_minutes, project)
    raise ValueError(f"unknown source: {source} (choose from {', '.join(ALL_SOURCES)})")
