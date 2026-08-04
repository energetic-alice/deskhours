"""Pure counting logic — no I/O, no OS calls."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Iterable

from deskhours.config import NOTIFY_THRESHOLD_H, SLOT_MINUTES

Slot = tuple[int, int]  # (hour, index_within_hour)


def slot_at(now: datetime, slot_minutes: int = SLOT_MINUTES) -> Slot:
    if slot_minutes <= 0 or 60 % slot_minutes != 0:
        raise ValueError("slot_minutes must be a positive divisor of 60")
    return now.hour, now.minute // slot_minutes


def hours_from_slots(slots: Iterable[Slot], slot_minutes: int = SLOT_MINUTES) -> float:
    return len(set(slots)) * (slot_minutes / 60.0)


def should_notify(
    hours: float,
    notified_hour: int,
    threshold: float = NOTIFY_THRESHOLD_H,
) -> int | None:
    """Return the whole-hour watermark to store if a reminder is due."""
    if hours < threshold:
        return None
    current = math.floor(hours)
    if current > notified_hour:
        return current
    return None


@dataclass
class DayState:
    day: str = field(default_factory=lambda: date.today().isoformat())
    slots: set[Slot] = field(default_factory=set)
    notified_hour: int = 0

    @classmethod
    def from_dict(cls, data: dict, *, today: str | None = None) -> DayState:
        today = today or date.today().isoformat()
        if data.get("date") != today:
            return cls(day=today)
        slots: set[Slot] = set()
        for item in data.get("slots", []):
            if isinstance(item, (list, tuple)) and len(item) == 2:
                slots.add((int(item[0]), int(item[1])))
        return cls(
            day=today,
            slots=slots,
            notified_hour=int(data.get("notified_hour", 0)),
        )

    def to_dict(self) -> dict:
        return {
            "date": self.day,
            "notified_hour": self.notified_hour,
            "slots": sorted([list(s) for s in self.slots]),
        }

    def mark(self, now: datetime, slot_minutes: int = SLOT_MINUTES) -> Slot:
        slot = slot_at(now, slot_minutes)
        self.slots.add(slot)
        return slot

    def hours(self, slot_minutes: int = SLOT_MINUTES) -> float:
        return hours_from_slots(self.slots, slot_minutes)

    def active_clock_hours(self) -> list[int]:
        return sorted({hour for hour, _ in self.slots})
