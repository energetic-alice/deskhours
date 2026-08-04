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


def _load(kind: str) -> ModuleType:
    name = backend_name()
    return importlib.import_module(f"deskhours.{kind}.{name}")


def idle_seconds() -> float:
    return float(_load("idle").idle_seconds())


def notify(title: str, message: str, *, dialog: bool = False) -> None:
    _load("notify").notify(title, message, dialog=dialog)
