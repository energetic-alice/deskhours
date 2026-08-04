"""macOS notifications via osascript."""

from __future__ import annotations

import subprocess


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def notify(title: str, message: str, *, dialog: bool = False) -> None:
    title_e = _escape(title)
    message_e = _escape(message)
    if dialog:
        script = (
            f'display dialog "{message_e}" buttons {{"OK"}} default button "OK" '
            f'with title "{title_e}" with icon caution'
        )
    else:
        script = (
            f'display notification "{message_e}" with title "{title_e}" '
            f'sound name "Glass"'
        )
    subprocess.run(["osascript", "-e", script], check=False)
