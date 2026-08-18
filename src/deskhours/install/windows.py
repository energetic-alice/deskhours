"""Windows Task Scheduler install / uninstall, through schtasks (no dependencies)."""

from __future__ import annotations

import getpass
import subprocess
import sys

from deskhours.config import APP_NAME, POLL_INTERVAL_SEC, Settings
from deskhours.install import program_arguments
from deskhours.state import default_state_path

TASK_NAME = APP_NAME


def poll_minutes(interval_seconds: int = POLL_INTERVAL_SEC) -> int:
    """schtasks counts in whole minutes and rejects zero."""
    return max(1, interval_seconds // 60)


def task_run_value(program: list[str]) -> str:
    """Fold the command into the single string /TR accepts.

    The program path is quoted even when it has no space, because a user profile path
    usually does. Later parts are quoted only when needed, which keeps the value short
    enough to stay clear of the length limit older Windows builds put on /TR.
    """
    head, *rest = program
    parts = [f'"{head}"'] + [f'"{p}"' if " " in p else p for p in rest]
    return " ".join(parts)


def create_command(program: list[str], name: str, minutes: int, user: str) -> list[str]:
    """Interactive on purpose: a reminder nobody can see is not a reminder.

    /IT ties the task to a logged-on session, which is what lets it put a window on the
    desktop, and it also means schtasks does not ask for a stored password.
    """
    return [
        "schtasks",
        "/Create",
        "/TN",
        name,
        "/TR",
        task_run_value(program),
        "/SC",
        "MINUTE",
        "/MO",
        str(minutes),
        "/RU",
        user,
        "/IT",
        "/F",
    ]


def delete_command(name: str) -> list[str]:
    return ["schtasks", "/Delete", "/TN", name, "/F"]


def query_command(name: str) -> list[str]:
    return ["schtasks", "/Query", "/TN", name]


def install(settings: Settings) -> int:
    program = program_arguments(settings)
    minutes = poll_minutes()
    command = create_command(program, TASK_NAME, minutes, getpass.getuser())

    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        print("deskhours: schtasks /Create failed", file=sys.stderr)
        return result.returncode

    print(f"Installed scheduled task: {TASK_NAME}")
    print(f"Counting: {settings.source}. Runs every {minutes} minutes.")
    print(f"State file: {default_state_path(settings.source)}")
    print("Using:", task_run_value(program))
    return 0


def uninstall() -> int:
    exists = subprocess.run(
        query_command(TASK_NAME), check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    if exists.returncode != 0:
        print("No scheduled task installed.")
        return 0

    result = subprocess.run(delete_command(TASK_NAME), check=False)
    if result.returncode != 0:
        print("deskhours: schtasks /Delete failed", file=sys.stderr)
        return result.returncode
    print(f"Removed scheduled task: {TASK_NAME}")
    return 0
