"""Defaults and shared constants."""

from __future__ import annotations

from dataclasses import dataclass

SLOT_MINUTES = 30
IDLE_THRESHOLD_SEC = 300
NOTIFY_THRESHOLD_H = 8.0
POLL_INTERVAL_SEC = 300

APP_NAME = "deskhours"
LAUNCH_AGENT_LABEL = "com.deskhours"

ALL_SOURCES = ("input", "agents")
DEFAULT_SOURCE = "input"

NOTIFY_TITLE = "Time to wrap up"
NOTIFY_MESSAGES = {
    "input": "You have been active at your computer for {hours:.1f}h today.",
    "agents": "You have been working with coding agents for {hours:.1f}h today.",
}


@dataclass(frozen=True)
class Settings:
    """What the background poller should be told to do.

    These six values travel together from the command line into the scheduler entry, so
    they move as one object rather than as six parameters repeated at every step.
    """

    source: str = DEFAULT_SOURCE
    project: str | None = None
    threshold: float = NOTIFY_THRESHOLD_H
    idle_threshold: int = IDLE_THRESHOLD_SEC
    slot: int = SLOT_MINUTES
    dialog: bool = False
