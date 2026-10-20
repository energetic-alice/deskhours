"""Background installer entrypoints."""

from __future__ import annotations

import shutil
import sys

from deskhours.config import Settings
from deskhours.platform import load_backend


def program_arguments(settings: Settings) -> list[str]:
    """The command the scheduler should run, shared by every platform.

    Prefer the installed console script: the scheduler runs outside any activated
    virtualenv, so `python -m deskhours` only works when that interpreter can already
    import the package.
    """
    exe = shutil.which("deskhours")
    args = [exe, "tick"] if exe else [sys.executable, "-m", "deskhours", "tick"]
    args += [
        "--threshold",
        str(settings.threshold),
        "--idle-threshold",
        str(settings.idle_threshold),
        "--slot",
        str(settings.slot),
        "--source",
        settings.source,
    ]
    if settings.project:
        args += ["--project", settings.project]
    if settings.dialog:
        args.append("--dialog")
    return args


def install(settings: Settings) -> int:
    return load_backend("install").install(settings)


def uninstall() -> int:
    return load_backend("install").uninstall()
