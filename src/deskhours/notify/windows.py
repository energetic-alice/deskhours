"""Windows notifications via MessageBox (stdlib)."""

from __future__ import annotations

import ctypes

MB_OK = 0x0
MB_ICONWARNING = 0x30
MB_ICONINFORMATION = 0x40


def notify(title: str, message: str, *, dialog: bool = False) -> None:
    flags = MB_OK | (MB_ICONWARNING if dialog else MB_ICONINFORMATION)
    ctypes.windll.user32.MessageBoxW(0, message, title, flags)
