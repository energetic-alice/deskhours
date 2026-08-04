"""Linux idle seconds (X11 via xprintidle)."""

from __future__ import annotations

import shutil
import subprocess


def idle_seconds() -> float:
    xprintidle = shutil.which("xprintidle")
    if not xprintidle:
        raise RuntimeError(
            "Linux idle probe needs `xprintidle` on PATH (X11). "
            "Wayland support is planned; see README."
        )
    out = subprocess.check_output([xprintidle], text=True).strip()
    return float(out) / 1000.0
