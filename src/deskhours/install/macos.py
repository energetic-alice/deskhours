"""macOS LaunchAgent install / uninstall."""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

from deskhours.config import APP_NAME, LAUNCH_AGENT_LABEL, POLL_INTERVAL_SEC, Settings
from deskhours.install import program_arguments
from deskhours.state import default_state_path

PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LAUNCH_AGENT_LABEL}.plist"


def render_plist(program: list[str]) -> str:
    arg_xml = "\n".join(f"            <string>{_xml_escape(a)}</string>" for a in program)
    return textwrap.dedent(
        f"""\
        <?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
        <plist version="1.0">
        <dict>
            <key>Label</key>
            <string>{LAUNCH_AGENT_LABEL}</string>
            <key>ProgramArguments</key>
            <array>
        {arg_xml}
            </array>
            <key>StartInterval</key>
            <integer>{POLL_INTERVAL_SEC}</integer>
            <key>RunAtLoad</key>
            <true/>
            <key>StandardOutPath</key>
            <string>/tmp/{APP_NAME}.log</string>
            <key>StandardErrorPath</key>
            <string>/tmp/{APP_NAME}.err</string>
        </dict>
        </plist>
        """
    )


def _xml_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


def install(settings: Settings) -> int:
    program = program_arguments(settings)
    plist = render_plist(program)
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)

    replaced = PLIST_PATH.exists()
    if replaced:
        subprocess.run(["launchctl", "unload", "-w", str(PLIST_PATH)], check=False)

    PLIST_PATH.write_text(plist, encoding="utf-8")
    result = subprocess.run(["launchctl", "load", "-w", str(PLIST_PATH)], check=False)
    if result.returncode != 0:
        print("deskhours: launchctl load failed", file=sys.stderr)
        return result.returncode

    print(f"{'Replaced' if replaced else 'Installed'} LaunchAgent: {PLIST_PATH}")
    print(f"Counting: {settings.source}. Polls every {POLL_INTERVAL_SEC // 60} minutes.")
    print(f"State file: {default_state_path(settings.source)}")
    print("Using:", " ".join(program))
    return 0


def uninstall() -> int:
    if not PLIST_PATH.exists():
        print("No LaunchAgent installed.")
        return 0
    subprocess.run(["launchctl", "unload", "-w", str(PLIST_PATH)], check=False)
    os.remove(PLIST_PATH)
    print(f"Removed {PLIST_PATH}")
    return 0
