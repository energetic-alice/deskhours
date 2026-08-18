"""macOS LaunchAgent install / uninstall."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

from deskhours.config import DEFAULT_SOURCE, LAUNCH_AGENT_LABEL, POLL_INTERVAL_SEC
from deskhours.state import default_state_path

LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"


def agent_label(source: str = DEFAULT_SOURCE) -> str:
    """One label per source, so the two pollers can run side by side.

    The default source keeps the plain label, which leaves an already-installed agent alone.
    """
    return LAUNCH_AGENT_LABEL if source == DEFAULT_SOURCE else f"{LAUNCH_AGENT_LABEL}.{source}"


def plist_path(source: str = DEFAULT_SOURCE) -> Path:
    return LAUNCH_AGENTS_DIR / f"{agent_label(source)}.plist"


def program_arguments(
    *,
    threshold: float,
    idle_threshold: int,
    slot: int,
    dialog: bool,
    source: str = DEFAULT_SOURCE,
    project: str | None = None,
) -> list[str]:
    exe = shutil.which("deskhours")
    if exe:
        args = [exe, "tick"]
    else:
        args = [sys.executable, "-m", "deskhours", "tick"]
    args += [
        "--threshold",
        str(threshold),
        "--idle-threshold",
        str(idle_threshold),
        "--slot",
        str(slot),
        "--source",
        source,
    ]
    if project:
        args += ["--project", project]
    if dialog:
        args.append("--dialog")
    return args


def render_plist(program: list[str], label: str = LAUNCH_AGENT_LABEL) -> str:
    arg_xml = "\n".join(f"            <string>{_xml_escape(a)}</string>" for a in program)
    return textwrap.dedent(
        f"""\
        <?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
        <plist version="1.0">
        <dict>
            <key>Label</key>
            <string>{label}</string>
            <key>ProgramArguments</key>
            <array>
        {arg_xml}
            </array>
            <key>StartInterval</key>
            <integer>{POLL_INTERVAL_SEC}</integer>
            <key>RunAtLoad</key>
            <true/>
            <key>StandardOutPath</key>
            <string>/tmp/{label}.log</string>
            <key>StandardErrorPath</key>
            <string>/tmp/{label}.err</string>
        </dict>
        </plist>
        """
    )


def _xml_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def install(
    *,
    threshold: float,
    idle_threshold: int,
    slot: int,
    dialog: bool,
    source: str = DEFAULT_SOURCE,
    project: str | None = None,
) -> int:
    program = program_arguments(
        threshold=threshold,
        idle_threshold=idle_threshold,
        slot=slot,
        dialog=dialog,
        source=source,
        project=project,
    )
    label = agent_label(source)
    path = plist_path(source)
    plist = render_plist(program, label)
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        subprocess.run(["launchctl", "unload", "-w", str(path)], check=False)

    path.write_text(plist, encoding="utf-8")
    result = subprocess.run(["launchctl", "load", "-w", str(path)], check=False)
    if result.returncode != 0:
        print("deskhours: launchctl load failed", file=sys.stderr)
        return result.returncode

    print(f"Installed LaunchAgent: {path}")
    print(
        f"Polls every {POLL_INTERVAL_SEC // 60} minutes. "
        f"State file: {default_state_path(source)}"
    )
    print("Using:", " ".join(program))
    return 0


def uninstall(source: str = DEFAULT_SOURCE) -> int:
    path = plist_path(source)
    if not path.exists():
        print(f"No LaunchAgent installed for source {source}.")
        return 0
    subprocess.run(["launchctl", "unload", "-w", str(path)], check=False)
    os.remove(path)
    print(f"Removed {path}")
    return 0
