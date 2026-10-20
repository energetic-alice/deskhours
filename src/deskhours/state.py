"""Day-state persistence (JSON on disk)."""

from __future__ import annotations

import json
import os
from pathlib import Path

from deskhours.config import APP_NAME, DEFAULT_SOURCE
from deskhours.core import DayState


def _state_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home())
        return base / APP_NAME
    xdg = os.environ.get("XDG_DATA_HOME")
    root = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return root / APP_NAME


def default_state_path(source: str = DEFAULT_SOURCE) -> Path:
    """Each source keeps its own file, because the two counts are not interchangeable.

    The default source keeps the original name so an already-installed poller does not
    lose the history it has collected.
    """
    name = "state.json" if source == DEFAULT_SOURCE else f"state-{source}.json"
    return _state_dir() / name


def load_state(
    path: Path | None = None, source: str = DEFAULT_SOURCE, *, today: str | None = None
) -> DayState:
    path = path or default_state_path(source)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    return DayState.from_dict(data, today=today)


def save_state(state: DayState, path: Path | None = None, source: str = DEFAULT_SOURCE) -> None:
    path = path or default_state_path(source)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(state.to_dict(), indent=2, sort_keys=True) + "\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(path)
