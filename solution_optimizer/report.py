"""Aggregation and rendering of adherence-check results.

`AdherenceReport` is what `diff_check.check_adherence` returns and what
`cli.py` prints. It is deliberately separate from `diff_check.py` so that
report presentation (markdown, summary strings) can evolve without
touching the classification logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Imported lazily inside diff_check.py to avoid a circular import; imported
# directly here since this module doesn't depend on diff_check.
from solution_optimizer.diff_check import SolutionVerdict


@dataclass
class AdherenceReport:
    """Aggregated adherence results for one transcript+diff pair.

    Attributes:
        results: One SolutionVerdict per StatedSolution that was checked.
    """

    results: list[SolutionVerdict] = field(default_factory=list)

    @property
    def determinable_results(self) -> list[SolutionVerdict]:
        """Results excluding 'no_file_reference' — the cases where
        adherence could actually be checked one way or the other."""
        return [r for r in self.results if r.verdict != "no_file_reference"]

    @property
    def applied_count(self) -> int:
        return sum(1 for r in self.results if r.verdict == "applied")

    @property
    def not_found_count(self) -> int:
        return sum(1 for r in self.results if r.verdict == "not_found")

    @property
    def no_file_reference_count(self) -> int:
        return sum(1 for r in self.results if r.verdict == "no_file_reference")

    @property
    def adherence_rate(self) -> float | None:
        """Fraction of *determinable* stated solutions that were applied.

        Only counts solutions where a file reference existed to check
        against (excludes 'no_file_reference'). Returns None when there
        are zero determinable results, since a rate would be meaningless
        (avoids a misleading 0.0 or division by zero).
        """
        determinable = self.determinable_results
        if not determinable:
            return None
        return self.applied_count / len(determinable)

    def summary(self) -> str:
        """A one-line human-readable summary."""
        total = len(self.results)
        rate = self.adherence_rate
        rate_str = f"{rate:.0%}" if rate is not None else "N/A (no determinable cases)"
        return (
            f"{total} stated solution(s): "
            f"{self.applied_count} applied, "
            f"{self.not_found_count} not found, "
            f"{self.no_file_reference_count} no file reference "
            f"-- adherence rate: {rate_str}"
        )

    def render_markdown(self) -> str:
        """Render a full markdown report."""
        lines = ["# Solution Adherence Report", "", self.summary(), ""]

        if not self.results:
            lines.append("_No stated solutions were extracted from this transcript._")
            return "\n".join(lines)

        lines.append("| # | Verdict | Matched File | Message # | Stated Text |")
        lines.append("|---|---------|--------------|-----------|-------------|")
        for i, r in enumerate(self.results, start=1):
            text = r.solution.text.replace("|", "\\|")
            if len(text) > 100:
                text = text[:97] + "..."
            matched = r.matched_path or "-"
            lines.append(
                f"| {i} | {r.verdict} | {matched} | {r.solution.message_index} | {text} |"
            )

        return "\n".join(lines)
