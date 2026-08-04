"""Background installer entrypoints."""

from __future__ import annotations

import sys

from deskhours.platform import UnsupportedPlatformError, backend_name


def install(*, threshold: float, idle_threshold: int, slot: int, dialog: bool) -> int:
    name = backend_name()
    if name == "macos":
        from deskhours.install import macos

        return macos.install(
            threshold=threshold,
            idle_threshold=idle_threshold,
            slot=slot,
            dialog=dialog,
        )
    raise UnsupportedPlatformError(
        f"deskhours install is not implemented for {sys.platform} yet. "
        "See packagers/ for drafts."
    )


def uninstall() -> int:
    name = backend_name()
    if name == "macos":
        from deskhours.install import macos

        return macos.uninstall()
    raise UnsupportedPlatformError(
        f"deskhours uninstall is not implemented for {sys.platform} yet."
    )
