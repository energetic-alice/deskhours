"""Command building for both schedulers, checked without touching either one."""

from __future__ import annotations

import plistlib

from deskhours import install
from deskhours.config import Settings
from deskhours.install import macos, windows


def test_program_arguments_carry_the_source_and_project(monkeypatch):
    monkeypatch.setattr(install.shutil, "which", lambda _: "/opt/bin/deskhours")
    args = install.program_arguments(Settings(source="agents", project="my api"))
    assert args[:2] == ["/opt/bin/deskhours", "tick"]
    assert args[-4:] == ["--source", "agents", "--project", "my api"]
    assert "--dialog" not in args


def test_program_arguments_fall_back_to_the_module(monkeypatch):
    """Without the console script on PATH the scheduler has to call the interpreter."""
    monkeypatch.setattr(install.shutil, "which", lambda _: None)
    args = install.program_arguments(Settings(dialog=True))
    assert args[1:4] == ["-m", "deskhours", "tick"]
    assert args[-1] == "--dialog"


def test_there_is_exactly_one_scheduler_entry():
    """Two jobs would fire two reminders for the same day; the source is a flag, not a job."""
    assert macos.PLIST_PATH.name == "com.deskhours.plist"
    assert windows.TASK_NAME == "deskhours"


def test_plist_is_valid_and_carries_the_chosen_source():
    program = ["/opt/bin/deskhours", "tick", "--source", "agents"]
    parsed = plistlib.loads(macos.render_plist(program).encode("utf-8"))
    assert parsed["Label"] == "com.deskhours"
    assert parsed["ProgramArguments"] == program
    assert parsed["StandardOutPath"] == "/tmp/deskhours.log"


def test_plist_escapes_a_path_that_would_break_the_xml():
    program = ["/opt/A & B/deskhours", "tick", "--project", "a<b>c"]
    parsed = plistlib.loads(macos.render_plist(program).encode("utf-8"))
    assert parsed["ProgramArguments"] == program


def test_windows_quotes_the_program_and_any_argument_with_a_space():
    value = windows.task_run_value(
        ["C:\\Program Files\\deskhours.exe", "tick", "--project", "my api", "--slot", "30"]
    )
    assert value == '"C:\\Program Files\\deskhours.exe" tick --project "my api" --slot 30'


def test_windows_create_command_repeats_every_five_minutes():
    command = windows.create_command(["deskhours", "tick"], windows.TASK_NAME, 5, "dev")
    assert command[:4] == ["schtasks", "/Create", "/TN", "deskhours"]
    assert command[command.index("/TR") + 1] == '"deskhours" tick'
    assert command[command.index("/SC") + 1] == "MINUTE"
    assert command[command.index("/MO") + 1] == "5"
    assert command[command.index("/RU") + 1] == "dev"
    assert "/IT" in command and "/F" in command


def test_windows_poll_never_asks_for_zero_minutes():
    assert windows.poll_minutes(300) == 5
    assert windows.poll_minutes(30) == 1


def test_delete_command_is_forced_so_it_does_not_prompt():
    assert windows.delete_command("deskhours") == [
        "schtasks",
        "/Delete",
        "/TN",
        "deskhours",
        "/F",
    ]
