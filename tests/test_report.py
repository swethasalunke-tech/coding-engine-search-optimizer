from solution_optimizer.diff_check import SolutionVerdict
from solution_optimizer.extract import StatedSolution
from solution_optimizer.report import AdherenceReport


def _solution(text="I'll fix x.py", idx=0, paths=None):
    return StatedSolution(text=text, message_index=idx, referenced_paths=paths or [])


def test_empty_report():
    report = AdherenceReport(results=[])
    assert report.applied_count == 0
    assert report.not_found_count == 0
    assert report.no_file_reference_count == 0
    assert report.adherence_rate is None
    assert "No stated solutions" in report.render_markdown()


def test_adherence_rate_only_counts_determinable_cases():
    results = [
        SolutionVerdict(solution=_solution(paths=["a.py"]), verdict="applied", matched_path="a.py"),
        SolutionVerdict(solution=_solution(paths=["b.py"]), verdict="not_found"),
        SolutionVerdict(solution=_solution(paths=[]), verdict="no_file_reference"),
    ]
    report = AdherenceReport(results=results)
    assert report.applied_count == 1
    assert report.not_found_count == 1
    assert report.no_file_reference_count == 1
    # determinable = applied + not_found = 2; applied = 1 -> rate 0.5
    assert report.adherence_rate == 0.5


def test_adherence_rate_all_applied():
    results = [
        SolutionVerdict(solution=_solution(), verdict="applied", matched_path="x.py"),
        SolutionVerdict(solution=_solution(), verdict="applied", matched_path="y.py"),
    ]
    report = AdherenceReport(results=results)
    assert report.adherence_rate == 1.0


def test_adherence_rate_none_when_only_undetermined():
    results = [
        SolutionVerdict(solution=_solution(paths=[]), verdict="no_file_reference"),
    ]
    report = AdherenceReport(results=results)
    assert report.adherence_rate is None


def test_summary_contains_counts():
    results = [
        SolutionVerdict(solution=_solution(), verdict="applied", matched_path="x.py"),
        SolutionVerdict(solution=_solution(), verdict="not_found"),
    ]
    report = AdherenceReport(results=results)
    summary = report.summary()
    assert "2 stated solution(s)" in summary
    assert "1 applied" in summary
    assert "1 not found" in summary
    assert "50%" in summary


def test_render_markdown_contains_table_and_rows():
    results = [
        SolutionVerdict(
            solution=_solution(text="I'll fix x.py", idx=3, paths=["x.py"]),
            verdict="applied",
            matched_path="x.py",
        ),
    ]
    report = AdherenceReport(results=results)
    md = report.render_markdown()
    assert "# Solution Adherence Report" in md
    assert "| # | Verdict | Matched File | Message # | Stated Text |" in md
    assert "applied" in md
    assert "x.py" in md
    assert "3" in md


def test_render_markdown_escapes_pipe_and_truncates_long_text():
    long_text = "I'll do a very long thing " + ("x" * 200) + " in y.py"
    results = [
        SolutionVerdict(
            solution=_solution(text=long_text, idx=0, paths=["y.py"]),
            verdict="applied",
            matched_path="y.py",
        ),
    ]
    report = AdherenceReport(results=results)
    md = report.render_markdown()
    assert "..." in md
