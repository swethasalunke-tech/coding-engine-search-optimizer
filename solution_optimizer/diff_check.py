"""Unified-diff parsing and stated-solution adherence checking.

This module parses standard `git diff` / unified-diff text (the kind
produced by `git diff` or `diff -u`) using only `re` and string
processing — no external diff library. It then checks each
`StatedSolution` extracted from a transcript against the set of files that
were actually changed in the diff.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Literal

from solution_optimizer.extract import StatedSolution

# Matches the "diff --git a/path b/path" header that starts a new file's
# section in a unified diff.
_DIFF_GIT_HEADER_RE = re.compile(r"^diff --git a/(.+?) b/(.+?)$")

# Matches "+++ b/path" (or "+++ path", or "+++ /dev/null" for deletions).
_PLUS_HEADER_RE = re.compile(r"^\+\+\+ (?:b/)?(.+)$")

# Matches "--- a/path" (or "--- path", or "--- /dev/null" for new files).
_MINUS_HEADER_RE = re.compile(r"^--- (?:a/)?(.+)$")

Verdict = Literal["applied", "not_found", "no_file_reference"]


def parse_unified_diff(diff_text: str) -> dict[str, list[str]]:
    """Parse unified-diff text into a mapping of changed file path -> list
    of added lines (content only, without the leading '+').

    Recognizes standard `diff --git a/x b/y` / `--- a/x` / `+++ b/y` /
    `@@ ... @@` unified diff hunks. Lines starting with '+' inside a hunk
    (except the '+++' file header itself) are treated as added lines.
    Deleted lines ('-') and context lines (' ') are not included in the
    returned added-lines lists, but files that only had deletions still
    appear in the result mapped to an empty list, so callers can tell a
    file was touched even with no additions.
    """
    changed: dict[str, list[str]] = {}
    current_path: str | None = None

    lines = diff_text.splitlines()
    for line in lines:
        git_header = _DIFF_GIT_HEADER_RE.match(line)
        if git_header:
            # Prefer the b/ (post-change) path; fall back handled by +++ below.
            current_path = git_header.group(2)
            changed.setdefault(current_path, [])
            continue

        if line.startswith("+++"):
            m = _PLUS_HEADER_RE.match(line)
            if m:
                path = m.group(1).strip()
                if path != "/dev/null":
                    current_path = path
                    changed.setdefault(current_path, [])
            continue

        if line.startswith("---"):
            # Only used to confirm a new file section; the actual tracked
            # path comes from +++ (or the diff --git header).
            continue

        if line.startswith("@@"):
            continue

        if current_path is None:
            continue

        if line.startswith("+"):
            changed[current_path].append(line[1:])
        # '-' (deletion) and ' ' (context) lines intentionally ignored.

    return changed


@dataclass(frozen=True)
class SolutionVerdict:
    """The adherence verdict for a single StatedSolution."""

    solution: StatedSolution
    verdict: Verdict
    matched_path: str | None = None


@dataclass
class AdherenceReportData:
    """Raw aggregation input, kept separate from the presentation logic in
    report.py. See report.AdherenceReport for the object callers should
    actually use.
    """

    results: list[SolutionVerdict] = field(default_factory=list)


def _paths_match(referenced: str, changed_path: str) -> bool:
    """A referenced path "matches" a changed file if it's an exact string
    match, or if their basenames match (handles cases like the assistant
    referencing "utils.py" while the diff header says "src/utils.py").
    """
    if referenced == changed_path:
        return True
    return os.path.basename(referenced) == os.path.basename(changed_path)


def check_adherence(
    stated_solutions: list[StatedSolution], diff_text: str
) -> "AdherenceReport":
    """Classify each StatedSolution's adherence against a unified diff.

    Classification rules:
      - "no_file_reference": the extractor found no referenced_paths for
        this solution, so there is nothing to check adherence against.
        This is an *undetermined* case, not a lie — it is excluded from
        the adherence_rate denominator (see report.py).
      - "applied": at least one referenced path matches (exact or
        basename) a file present in the parsed diff.
      - "not_found": referenced_paths is non-empty, but none of them
        match any changed file in the diff.
    """
    from solution_optimizer.report import AdherenceReport  # local import: avoid cycle

    changed_files = parse_unified_diff(diff_text)
    results: list[SolutionVerdict] = []

    for solution in stated_solutions:
        if not solution.referenced_paths:
            results.append(SolutionVerdict(solution=solution, verdict="no_file_reference"))
            continue

        matched_path = None
        for ref in solution.referenced_paths:
            for changed_path in changed_files:
                if _paths_match(ref, changed_path):
                    matched_path = changed_path
                    break
            if matched_path:
                break

        if matched_path:
            results.append(
                SolutionVerdict(solution=solution, verdict="applied", matched_path=matched_path)
            )
        else:
            results.append(SolutionVerdict(solution=solution, verdict="not_found"))

    return AdherenceReport(results=results)
