"""Linux notifications via notify-send (best effort)."""

from __future__ import annotations

import shutil
import subprocess
import sys


def notify(title: str, message: str, *, dialog: bool = False) -> None:
    del dialog  # no portable modal on Linux desktops
    notify_send = shutil.which("notify-send")
    if notify_send:
        subprocess.run([notify_send, title, message], check=False)
        return
    print(f"{title}: {message}", file=sys.stderr)
