"""Day-state persistence (JSON on disk)."""

from __future__ import annotations

import json
import os
from pathlib import Path

from deskhours.config import APP_NAME
from deskhours.core import DayState


def default_state_path() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home())
        return base / APP_NAME / "state.json"
    xdg = os.environ.get("XDG_DATA_HOME")
    root = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return root / APP_NAME / "state.json"


def load_state(path: Path | None = None) -> DayState:
    path = path or default_state_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    return DayState.from_dict(data)


def save_state(state: DayState, path: Path | None = None) -> None:
    path = path or default_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(state.to_dict(), indent=2, sort_keys=True) + "\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(path)
