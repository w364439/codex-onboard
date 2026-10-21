"""Behavioural tests for codex-onboard.

Each test builds a throwaway repository on disk so the checks are exercised
against real files rather than mocks.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from codex_onboard.checks import run_checks
from codex_onboard.cli import main
from codex_onboard.model import Report, Result, Severity
from codex_onboard.reporters import render_json, render_text

# Assembled at runtime on purpose: a literal here would trip this repository's
# own `secrets` check, and weakening the check to allow it would be worse.
FAKE_AWS_KEY = "AKIA" + "IOSFODNN7EXAMPLE"


def make_repo(base: Path, *, good: bool = True) -> Path:
    """Create a minimal repository; ``good`` decides whether it passes."""
    base.mkdir(parents=True, exist_ok=True)
    (base / ".gitignore").write_text("__pycache__/\n*.pyc\n.venv/\n", encoding="utf-8")
    if good:
        (base / "AGENTS.md").write_text("# Agents\n\nRun `pytest` before committing.\n", encoding="utf-8")
        (base / "README.md").write_text(
            "# demo\n\n## Install\n\npip install -e .\n\n## Usage\n\npython -m demo\n\n"
            + ("Long enough description so the README clears the length threshold. " * 4),
            encoding="utf-8",
        )
        (base / "LICENSE").write_text("MIT\n", encoding="utf-8")
        (base / ".python-version").write_text("3.12\n", encoding="utf-8")
        (base / "uv.lock").write_text("version = 1\n", encoding="utf-8")
        tests = base / "tests"
        tests.mkdir(exist_ok=True)
        (tests / "test_demo.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
        workflows = base / ".github" / "workflows"
        workflows.mkdir(parents=True, exist_ok=True)
        (workflows / "ci.yml").write_text("on: push\njobs:\n  t:\n    runs-on: ubuntu-latest\n", encoding="utf-8")
    return base


class ReportModelTests(unittest.TestCase):
    def test_empty_report_scores_zero_not_full(self):
        self.assertEqual(Report(root="x").score, 0)

    def test_score_is_weighted(self):
        report = Report(root="x")
        report.add(Result("a", "blocker passes", Severity.BLOCKER, True, ""))
        report.add(Result("b", "low fails", Severity.LOW, False, ""))
        self.assertEqual(report.score, round(100 * 20 / 22))

    def test_grade_thresholds(self):
        report = Report(root="x")
        report.add(Result("a", "only", Severity.BLOCKER, True, ""))
        self.assertEqual(report.score, 100)
        self.assertEqual(report.grade(), "A")

    def test_failures_sorted_by_severity(self):
        report = Report(root="x")
        report.add(Result("low", "l", Severity.LOW, False, ""))
        report.add(Result("blocker", "b", Severity.BLOCKER, False, ""))
        self.assertEqual([r.check_id for r in report.failures], ["blocker", "low"])


class CheckTests(unittest.TestCase):
    def test_clean_repo_passes_every_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_repo(Path(tmp) / "good")
            report = run_checks(root)
            self.assertEqual(report.failures, [], [f"{r.check_id}: {r.detail}" for r in report.failures])
            self.assertEqual(report.score, 100)

    def test_empty_repo_fails_blockers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "empty"
            root.mkdir()
            report = run_checks(root)
            failed = {r.check_id for r in report.failures}
            self.assertIn("agent-instructions", failed)
            self.assertIn("readme", failed)
            self.assertIn("ci", failed)
            self.assertLess(report.score, 50)

    def test_missing_agent_instructions_is_blocker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_repo(Path(tmp) / "noagents", good=True)
            (root / "AGENTS.md").unlink()
            report = run_checks(root)
            by_id = {r.check_id: r for r in report.results}
            self.assertFalse(by_id["agent-instructions"].passed)
            self.assertEqual(by_id["agent-instructions"].severity, Severity.BLOCKER)

    def test_thin_readme_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_repo(Path(tmp) / "thin")
            (root / "README.md").write_text("# hi\n", encoding="utf-8")
            by_id = {r.check_id: r for r in run_checks(root).results}
            self.assertFalse(by_id["readme"].passed)

    def test_readme_without_run_section_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_repo(Path(tmp) / "norun")
            (root / "README.md").write_text("# demo\n\n" + ("Prose only, no commands at all. " * 20), encoding="utf-8")
            by_id = {r.check_id: r for r in run_checks(root).results}
            self.assertFalse(by_id["readme"].passed)

    def test_committed_aws_key_is_blocker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_repo(Path(tmp) / "leak")
            (root / "config.py").write_text(f'KEY = "{FAKE_AWS_KEY}"\n', encoding="utf-8")
            by_id = {r.check_id: r for r in run_checks(root).results}
            self.assertFalse(by_id["secrets"].passed)
            self.assertIn("AWS access key", by_id["secrets"].detail)

    def test_placeholder_secret_is_not_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_repo(Path(tmp) / "safe")
            (root / "config.py").write_text('API_KEY = os.environ["API_KEY"]\n', encoding="utf-8")
            by_id = {r.check_id: r for r in run_checks(root).results}
            self.assertTrue(by_id["secrets"].passed)

    def test_noise_directories_are_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_repo(Path(tmp) / "noise")
            junk = root / "node_modules" / "pkg"
            junk.mkdir(parents=True)
            (junk / "leak.js").write_text(f'const k = "{FAKE_AWS_KEY}";\n', encoding="utf-8")
            by_id = {r.check_id: r for r in run_checks(root).results}
            self.assertTrue(by_id["secrets"].passed, "vendored deps must not be scanned")

    def test_fully_pinned_requirements_counts_as_lockfile(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_repo(Path(tmp) / "pinned")
            (root / "uv.lock").unlink()
            (root / "requirements.txt").write_text("requests==2.32.3\nclick==8.1.7\n", encoding="utf-8")
            by_id = {r.check_id: r for r in run_checks(root).results}
            self.assertTrue(by_id["lockfile"].passed)

    def test_unpinned_requirements_does_not_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_repo(Path(tmp) / "unpinned")
            (root / "uv.lock").unlink()
            (root / "requirements.txt").write_text("requests>=2.0\nclick\n", encoding="utf-8")
            by_id = {r.check_id: r for r in run_checks(root).results}
            self.assertFalse(by_id["lockfile"].passed)


class ReporterTests(unittest.TestCase):
    def test_json_is_valid_and_round_trips(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = run_checks(make_repo(Path(tmp) / "good"))
            payload = json.loads(render_json(report))
            self.assertEqual(payload["score"], 100)
            self.assertTrue(payload["passed"])
            self.assertEqual(len(payload["checks"]), len(report.results))

    def test_text_has_no_ansi_when_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = run_checks(make_repo(Path(tmp) / "good"))
            self.assertNotIn("\033[", render_text(report, color=False))


class CliTests(unittest.TestCase):
    def test_exit_zero_on_good_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_repo(Path(tmp) / "good")
            self.assertEqual(main([str(root), "--no-color"]), 0)

    def test_min_score_fails_bad_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "empty"
            root.mkdir()
            self.assertEqual(main([str(root), "--json", "--min-score", "60"]), 1)

    def test_missing_directory_returns_two(self):
        self.assertEqual(main(["/definitely/not/here", "--no-color"]), 2)


if __name__ == "__main__":
    unittest.main()
