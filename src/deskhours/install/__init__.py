"""Background installer entrypoints."""

from __future__ import annotations

import shutil
import sys

from deskhours.config import DEFAULT_SOURCE
from deskhours.platform import UnsupportedPlatformError, backend_name


def program_arguments(
    *,
    threshold: float,
    idle_threshold: int,
    slot: int,
    dialog: bool,
    source: str = DEFAULT_SOURCE,
    project: str | None = None,
) -> list[str]:
    """The command the scheduler should run, shared by every platform.

    Prefer the installed console script: the scheduler runs outside any activated
    virtualenv, so `python -m deskhours` only works when that interpreter can already
    import the package.
    """
    exe = shutil.which("deskhours")
    if exe:
        args = [exe, "tick"]
    else:
        args = [sys.executable, "-m", "deskhours", "tick"]
    args += [
        "--threshold",
        str(threshold),
        "--idle-threshold",
        str(idle_threshold),
        "--slot",
        str(slot),
        "--source",
        source,
    ]
    if project:
        args += ["--project", project]
    if dialog:
        args.append("--dialog")
    return args


def install(
    *,
    threshold: float,
    idle_threshold: int,
    slot: int,
    dialog: bool,
    source: str = DEFAULT_SOURCE,
    project: str | None = None,
) -> int:
    backend = _backend()
    return backend.install(
        threshold=threshold,
        idle_threshold=idle_threshold,
        slot=slot,
        dialog=dialog,
        source=source,
        project=project,
    )


def uninstall() -> int:
    return _backend().uninstall()


def _backend():
    name = backend_name()
    if name == "macos":
        from deskhours.install import macos

        return macos
    if name == "windows":
        from deskhours.install import windows

        return windows
    raise UnsupportedPlatformError(
        f"deskhours install is not implemented for {sys.platform} yet. "
        "See packagers/ for drafts."
    )
