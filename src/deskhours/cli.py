"""CLI entrypoint — argument parsing only; logic lives elsewhere."""

from __future__ import annotations

import argparse
import sys

from deskhours import __version__, install
from deskhours.config import (
    IDLE_THRESHOLD_SEC,
    NOTIFY_THRESHOLD_H,
    SLOT_MINUTES,
)
from deskhours.platform import UnsupportedPlatformError
from deskhours.tick import format_status, run_tick


def _add_common(parser: argparse.ArgumentParser) -> None:
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
        help=f"seconds without input before idle (default: {IDLE_THRESHOLD_SEC})",
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
            idle_threshold=args.idle_threshold,
            slot_minutes=args.slot,
            notify_threshold=args.threshold,
            dry_run=args.dry_run,
            dialog=args.dialog,
        )
    except (UnsupportedPlatformError, RuntimeError, OSError) as exc:
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


def cmd_install(args: argparse.Namespace) -> int:
    try:
        return install.install(
            threshold=args.threshold,
            idle_threshold=args.idle_threshold,
            slot=args.slot,
            dialog=args.dialog,
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
        description="Count computer activity hours from keyboard/mouse idle state.",
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

    install_p = sub.add_parser("install", help="install background poller (macOS)")
    _add_common(install_p)
    install_p.set_defaults(func=cmd_install)

    uninstall_p = sub.add_parser("uninstall", help="remove background poller (macOS)")
    uninstall_p.set_defaults(func=cmd_uninstall)

    return parser


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if not argv or argv[0].startswith("-"):
        argv = ["tick", *argv]
    args = build_parser().parse_args(argv)
    return args.func(args)
