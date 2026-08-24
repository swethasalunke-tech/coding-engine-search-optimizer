import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_cli_audit_runs_end_to_end_and_exits_zero():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "solution_optimizer.cli",
            "audit",
            "--transcript",
            str(FIXTURES_DIR / "transcript_basic.json"),
            "--diff",
            str(FIXTURES_DIR / "diff_basic.diff"),
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert result.stdout.strip() != ""
    assert "Solution Adherence Report" in result.stdout
    assert "applied" in result.stdout
    assert "not_found" in result.stdout


def test_cli_audit_missing_transcript_exits_nonzero():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "solution_optimizer.cli",
            "audit",
            "--transcript",
            str(FIXTURES_DIR / "does_not_exist.json"),
            "--diff",
            str(FIXTURES_DIR / "diff_basic.diff"),
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode != 0
    assert "error" in result.stderr.lower()


def test_cli_no_command_exits_nonzero():
    result = subprocess.run(
        [sys.executable, "-m", "solution_optimizer.cli"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode != 0
