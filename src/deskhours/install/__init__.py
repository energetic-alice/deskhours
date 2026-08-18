"""Background installer entrypoints."""

from __future__ import annotations

import sys

from deskhours.config import DEFAULT_SOURCE
from deskhours.platform import UnsupportedPlatformError, backend_name


def install(
    *,
    threshold: float,
    idle_threshold: int,
    slot: int,
    dialog: bool,
    source: str = DEFAULT_SOURCE,
    project: str | None = None,
) -> int:
    name = backend_name()
    if name == "macos":
        from deskhours.install import macos

        return macos.install(
            threshold=threshold,
            idle_threshold=idle_threshold,
            slot=slot,
            dialog=dialog,
            source=source,
            project=project,
        )
    raise UnsupportedPlatformError(
        f"deskhours install is not implemented for {sys.platform} yet. "
        "See packagers/ for drafts."
    )


def uninstall(source: str = DEFAULT_SOURCE) -> int:
    name = backend_name()
    if name == "macos":
        from deskhours.install import macos

        return macos.uninstall(source)
    raise UnsupportedPlatformError(
        f"deskhours uninstall is not implemented for {sys.platform} yet."
    )
