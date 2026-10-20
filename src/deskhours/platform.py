"""OS detection and lazy backend loading for idle + notify."""

from __future__ import annotations

import importlib
import sys
from types import ModuleType


class UnsupportedPlatformError(RuntimeError):
    pass


_BACKENDS = {
    "darwin": "macos",
    "win32": "windows",
}


def backend_name(platform: str | None = None) -> str:
    platform = platform or sys.platform
    if platform.startswith("linux"):
        return "linux"
    try:
        return _BACKENDS[platform]
    except KeyError as exc:
        raise UnsupportedPlatformError(f"Unsupported platform: {platform}") from exc


def load_backend(kind: str) -> ModuleType:
    """The implementation of one capability for the system we are running on.

    Every capability follows the same layout, `deskhours.<kind>.<system>`, so one lookup
    serves them all. A capability that has no module for this system is a gap in the port
    rather than a bug, and says so.
    """
    name = backend_name()
    try:
        return importlib.import_module(f"deskhours.{kind}.{name}")
    except ModuleNotFoundError as exc:
        raise UnsupportedPlatformError(
            f"deskhours {kind} is not implemented for {name} yet. See packagers/ for drafts."
        ) from exc


def idle_seconds() -> float:
    return float(load_backend("idle").idle_seconds())


def notify(title: str, message: str, *, dialog: bool = False) -> None:
    load_backend("notify").notify(title, message, dialog=dialog)
