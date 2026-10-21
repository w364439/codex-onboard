"""Command line entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .checks import run_checks
from .reporters import render_json, render_text


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codex-onboard",
        description="Audit a repository for AI coding-agent readiness.",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="repository root to audit (default: current directory)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit machine-readable JSON instead of text",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="disable ANSI colors",
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=0,
        metavar="N",
        help="exit non-zero when the score is below N (default: 0)",
    )
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.path).expanduser()
    if not root.is_dir():
        print(f"error: not a directory: {root}", file=sys.stderr)
        return 2

    report = run_checks(root.resolve())

    if args.json:
        print(render_json(report))
    else:
        print(render_text(report, color=not args.no_color))

    if report.score < args.min_score:
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
