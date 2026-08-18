"""CLI entrypoint — argument parsing only; logic lives elsewhere."""

from __future__ import annotations

import argparse
import sys

from deskhours import __version__, install
from deskhours.config import (
    ALL_SOURCES,
    DEFAULT_SOURCE,
    IDLE_THRESHOLD_SEC,
    NOTIFY_THRESHOLD_H,
    SLOT_MINUTES,
)
from deskhours.platform import UnsupportedPlatformError
from deskhours.tick import format_status, run_tick


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--source",
        choices=ALL_SOURCES,
        default=DEFAULT_SOURCE,
        help=(
            "what counts as working: keyboard and mouse activity (input) "
            f"or prompts sent to coding agents (agents) (default: {DEFAULT_SOURCE})"
        ),
    )
    parser.add_argument(
        "--project",
        help="with --source agents, count only sessions of projects matching this name",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=NOTIFY_THRESHOLD_H,
        help=f"notify from this many active hours (default: {NOTIFY_THRESHOLD_H:g})",
    )
    parser.add_argument(
        "--idle-threshold",
        type=int,
        default=IDLE_THRESHOLD_SEC,
        help=f"seconds without input before idle, --source input only "
        f"(default: {IDLE_THRESHOLD_SEC})",
    )
    parser.add_argument(
        "--slot",
        type=int,
        default=SLOT_MINUTES,
        help=f"slot size in minutes (default: {SLOT_MINUTES})",
    )
    parser.add_argument(
        "--dialog",
        action="store_true",
        help="use a modal dialog instead of a banner notification",
    )


def cmd_tick(args: argparse.Namespace) -> int:
    try:
        result = run_tick(
            source=args.source,
            project=args.project,
            idle_threshold=args.idle_threshold,
            slot_minutes=args.slot,
            notify_threshold=args.threshold,
            dry_run=args.dry_run,
            dialog=args.dialog,
        )
    except (UnsupportedPlatformError, RuntimeError, OSError, ValueError) as exc:
        print(f"deskhours: {exc}", file=sys.stderr)
        return 1

    if args.dry_run or args.verbose:
        print(
            format_status(
                result,
                slot_minutes=args.slot,
                notify_threshold=args.threshold,
            )
        )
    return 0


def cmd_sources(args: argparse.Namespace) -> int:
    """Show where each harness is read from and what came back.

    On a new machine this is the difference between trusting the number and knowing why a
    harness contributed nothing: not installed, moved, or simply unused that day.
    """
    from deskhours import transcripts

    _, per_harness = transcripts.collect_all(slot_minutes=args.slot, project=args.project)
    for harness, roots in transcripts.all_roots().items():
        prompts, day_count = per_harness[harness]
        note = "" if prompts else "   <- nothing found"
        print(f"{harness:<7} {prompts:>6} prompts  {day_count:>4} days{note}")
        for root in roots:
            print(f"        {'ok     ' if root.is_dir() else 'missing'}  {root}")

    if args.scan:
        print(f"\nSearching {args.scan} for other installs. This can take a while.")
        for harness, found in transcripts.scan(args.scan).items():
            for path in found:
                print(f"        found    {path}  ({harness})")
        print("Copies inside a sandboxed agent session are left out on purpose.")
        print(f"To use one of these, set {' or '.join(transcripts.ENV_OVERRIDES.values())}.")
        return 0

    print("\nLooked under:", ", ".join(str(p) for p in transcripts.candidate_parents()))
    print("A harness kept somewhere else can be pointed at with DESKHOURS_CURSOR_ROOT,")
    print("DESKHOURS_CLAUDE_ROOT or DESKHOURS_CODEX_ROOTS, or searched for with --scan DIR.")
    return 0


def cmd_install(args: argparse.Namespace) -> int:
    try:
        return install.install(
            threshold=args.threshold,
            idle_threshold=args.idle_threshold,
            slot=args.slot,
            dialog=args.dialog,
            source=args.source,
            project=args.project,
        )
    except UnsupportedPlatformError as exc:
        print(f"deskhours: {exc}", file=sys.stderr)
        return 1


def cmd_uninstall(_args: argparse.Namespace) -> int:
    try:
        return install.uninstall()
    except UnsupportedPlatformError as exc:
        print(f"deskhours: {exc}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="deskhours",
        description="Count working hours from keyboard and mouse activity, or from coding-agent prompts.",
    )
    parser.add_argument("--version", action="version", version=f"deskhours {__version__}")
    sub = parser.add_subparsers(dest="command")

    tick = sub.add_parser("tick", help="poll once (default command)")
    _add_common(tick)
    tick.add_argument(
        "--dry-run",
        action="store_true",
        help="print status without saving or notifying",
    )
    tick.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="print status after a real tick",
    )
    tick.set_defaults(func=cmd_tick, dry_run=False, verbose=False)

    status = sub.add_parser("status", help="show today's active hours (no save, no notify)")
    _add_common(status)
    status.set_defaults(func=cmd_tick, dry_run=True, verbose=False)

    sources_p = sub.add_parser(
        "sources", help="show which transcript directories are found on this machine"
    )
    sources_p.add_argument(
        "--project",
        help="count only sessions of projects matching this name",
    )
    sources_p.add_argument(
        "--slot",
        type=int,
        default=SLOT_MINUTES,
        help=f"slot size in minutes (default: {SLOT_MINUTES})",
    )
    sources_p.add_argument(
        "--scan",
        metavar="DIR",
        help="also search this directory tree for a harness kept somewhere unusual",
    )
    sources_p.set_defaults(func=cmd_sources)

    install_p = sub.add_parser(
        "install", help="install background poller (macOS LaunchAgent, Windows Task Scheduler)"
    )
    _add_common(install_p)
    install_p.set_defaults(func=cmd_install)

    uninstall_p = sub.add_parser("uninstall", help="remove background poller")
    uninstall_p.set_defaults(func=cmd_uninstall)

    return parser


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if not argv or argv[0].startswith("-"):
        argv = ["tick", *argv]
    args = build_parser().parse_args(argv)
    return args.func(args)
