from pathlib import Path

from solution_optimizer.diff_check import check_adherence, parse_unified_diff
from solution_optimizer.extract import StatedSolution
from solution_optimizer.report import AdherenceReport

FIXTURES_DIR = Path(__file__).parent / "fixtures"

SAMPLE_DIFF = (FIXTURES_DIR / "diff_basic.diff").read_text()


def test_parse_unified_diff_finds_changed_files():
    changed = parse_unified_diff(SAMPLE_DIFF)
    assert "auth.py" in changed
    assert "config.py" in changed


def test_parse_unified_diff_captures_added_lines():
    changed = parse_unified_diff(SAMPLE_DIFF)
    auth_added = changed["auth.py"]
    assert "        new_token = issue_new_token(token)" in auth_added
    assert "        return new_token" in auth_added
    assert any("fixed token refresh bug" in line for line in auth_added)
    # Deleted / context lines should not appear.
    assert "        return None" not in auth_added


def test_parse_unified_diff_ignores_deletions():
    changed = parse_unified_diff(SAMPLE_DIFF)
    config_added = changed["config.py"]
    assert "TIMEOUT_SECONDS = 30" in config_added
    assert "TIMEOUT_SECONDS = 5" not in config_added


def test_parse_unified_diff_empty_input():
    assert parse_unified_diff("") == {}


def test_parse_unified_diff_no_git_header_still_finds_plus_plus_plus():
    diff_text = (
        "--- a/foo.py\n"
        "+++ b/foo.py\n"
        "@@ -1,2 +1,2 @@\n"
        "-old line\n"
        "+new line\n"
    )
    changed = parse_unified_diff(diff_text)
    assert changed == {"foo.py": ["new line"]}


def test_check_adherence_applied_exact_match():
    solution = StatedSolution(text="I'll fix auth.py", message_index=0, referenced_paths=["auth.py"])
    report = check_adherence([solution], SAMPLE_DIFF)
    assert isinstance(report, AdherenceReport)
    assert len(report.results) == 1
    assert report.results[0].verdict == "applied"
    assert report.results[0].matched_path == "auth.py"


def test_check_adherence_applied_basename_match():
    solution = StatedSolution(
        text="I'll fix src/auth.py", message_index=0, referenced_paths=["src/auth.py"]
    )
    # diff has "auth.py" (no directory) -- basename match should still succeed.
    report = check_adherence([solution], SAMPLE_DIFF)
    assert report.results[0].verdict == "applied"
    assert report.results[0].matched_path == "auth.py"


def test_check_adherence_not_found():
    solution = StatedSolution(
        text="I'll add a test in test_auth.py",
        message_index=1,
        referenced_paths=["test_auth.py"],
    )
    report = check_adherence([solution], SAMPLE_DIFF)
    assert report.results[0].verdict == "not_found"
    assert report.results[0].matched_path is None


def test_check_adherence_no_file_reference():
    solution = StatedSolution(text="I'll clean this up.", message_index=0, referenced_paths=[])
    report = check_adherence([solution], SAMPLE_DIFF)
    assert report.results[0].verdict == "no_file_reference"
    assert report.results[0].matched_path is None


def test_check_adherence_mixed_batch():
    solutions = [
        StatedSolution(text="I'll fix auth.py", message_index=0, referenced_paths=["auth.py"]),
        StatedSolution(
            text="Let's add test_auth.py", message_index=1, referenced_paths=["test_auth.py"]
        ),
        StatedSolution(text="I'll clean this up.", message_index=2, referenced_paths=[]),
    ]
    report = check_adherence(solutions, SAMPLE_DIFF)
    verdicts = [r.verdict for r in report.results]
    assert verdicts == ["applied", "not_found", "no_file_reference"]
