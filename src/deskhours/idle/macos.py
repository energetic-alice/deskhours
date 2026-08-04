"""macOS idle seconds via IOHIDSystem (stdlib only)."""

from __future__ import annotations

import subprocess


def idle_seconds() -> float:
    out = subprocess.check_output(["ioreg", "-c", "IOHIDSystem"], text=True)
    for line in out.splitlines():
        if "HIDIdleTime" not in line:
            continue
        nanoseconds = int(line.split("=")[-1].strip())
        return nanoseconds / 1_000_000_000
    raise RuntimeError("HIDIdleTime not found in ioreg output")
