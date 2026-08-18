"""Defaults and shared constants."""

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
