"""Command-line entry point for the free, single-session audit pipeline.

Usage:
    python -m solution_optimizer.cli audit --transcript path.json --diff path.diff

This runs the full free pipeline end-to-end:
    1. Load and validate a Transcript from a JSON file.
    2. Extract StatedSolutions with the day-1 heuristic extractor.
    3. Parse the unified diff and check adherence.
    4. Print a markdown AdherenceReport to stdout.

No license is required for this path. The single-session CLI audit is free
forever — see DESIGN.md and README.md for the open-core split.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from solution_optimizer.diff_check import check_adherence
from solution_optimizer.extract import extract_stated_solutions
from solution_optimizer.schema import Transcript, TranscriptValidationError


def _load_transcript(path: str) -> Transcript:
    data = json.loads(Path(path).read_text())
    return Transcript.from_dict(data)


def _load_diff(path: str) -> str:
    return Path(path).read_text()


def cmd_audit(args: argparse.Namespace) -> int:
    try:
        transcript = _load_transcript(args.transcript)
    except (OSError, json.JSONDecodeError, TranscriptValidationError) as exc:
        print(f"error: failed to load transcript {args.transcript!r}: {exc}", file=sys.stderr)
        return 1

    try:
        diff_text = _load_diff(args.diff)
    except OSError as exc:
        print(f"error: failed to load diff {args.diff!r}: {exc}", file=sys.stderr)
        return 1

    stated_solutions = extract_stated_solutions(transcript)
    report = check_adherence(stated_solutions, diff_text)

    print(report.render_markdown())
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m solution_optimizer.cli",
        description=(
            "coding-engine-search-optimizer: audit whether a coding agent "
            "followed through on the solutions it stated mid-session. "
            "Free forever for single-session audits."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit_parser = subparsers.add_parser(
        "audit", help="Run the free single-session adherence audit."
    )
    audit_parser.add_argument(
        "--transcript", required=True, help="Path to a transcript JSON file."
    )
    audit_parser.add_argument(
        "--diff", required=True, help="Path to a unified diff text file."
    )
    audit_parser.set_defaults(func=cmd_audit)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
