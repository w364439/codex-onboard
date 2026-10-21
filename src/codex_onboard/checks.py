"""Individual readiness checks.

Every check is a pure function of the repository tree: it receives a
:class:`~codex_onboard.model.Report` plus a root path and appends results.
Nothing here shells out, so the audit is safe to run on an untrusted tree.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Callable, List

from .model import Report, Result, Severity

# Directories that never carry signal and are expensive to walk.
SKIP_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".mypy_cache",
    ".pytest_cache",
    "dist",
    "build",
    ".next",
    "target",
    "vendor",
}

AGENT_INSTRUCTION_FILES = ("AGENTS.md", "CLAUDE.md", ".cursorrules", "GEMINI.md")

LOCKFILES = (
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "poetry.lock",
    "Pipfile.lock",
    "uv.lock",
    "Cargo.lock",
    "go.sum",
    "composer.lock",
    "Gemfile.lock",
)

CI_PATHS = (
    ".github/workflows",
    ".gitlab-ci.yml",
    ".circleci",
    "azure-pipelines.yml",
    ".buildkite",
)

VERSION_PIN_FILES = (
    ".nvmrc",
    ".python-version",
    ".tool-versions",
    ".node-version",
    "rust-toolchain.toml",
    "rust-toolchain",
)

SECRET_PATTERNS = (
    ("AWS access key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("Private key block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("OpenAI-style key", re.compile(r"sk-[A-Za-z0-9]{32,}")),
    ("GitHub token", re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}")),
    ("Generic assignment", re.compile(r"(?i)\b(?:api[_-]?key|secret|password|token)\b\s*[:=]\s*['\"][^'\"]{16,}['\"]")),
)

# Files whose contents are scanned for leaked credentials.
SCAN_SUFFIXES = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".rb", ".java",
    ".sh", ".ps1", ".yml", ".yaml", ".json", ".toml", ".ini", ".env",
    ".cfg", ".conf", ".md",
}
MAX_SCAN_BYTES = 400_000


def _walk(root: Path):
    """Yield files, skipping noise directories."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            yield Path(dirpath) / name


def _exists_any(root: Path, names) -> List[str]:
    return [n for n in names if (root / n).exists()]


def check_agent_instructions(root: Path, report: Report) -> None:
    found = _exists_any(root, AGENT_INSTRUCTION_FILES)
    report.add(
        Result(
            check_id="agent-instructions",
            title="Agent instruction file present",
            severity=Severity.BLOCKER,
            passed=bool(found),
            detail=f"Found: {', '.join(found)}" if found else "No AGENTS.md / CLAUDE.md at repo root.",
            fix="Add AGENTS.md stating build, test, and lint commands plus conventions an agent must follow.",
        )
    )


def check_readme(root: Path, report: Report) -> None:
    candidates = [p for p in root.glob("README*") if p.is_file()]
    text = ""
    if candidates:
        try:
            text = candidates[0].read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
    has_run_section = bool(re.search(r"(?im)^#{1,6}\s*(install|setup|getting started|usage|quick ?start|运行|安装)", text))
    passed = bool(candidates) and len(text) >= 200 and has_run_section
    if not candidates:
        detail = "No README found."
    elif len(text) < 200:
        detail = f"README is only {len(text)} characters — too thin to onboard anyone."
    elif not has_run_section:
        detail = "README has no install/setup/usage section."
    else:
        detail = f"{candidates[0].name}: {len(text)} characters with a run section."
    report.add(
        Result(
            check_id="readme",
            title="README explains how to run the project",
            severity=Severity.BLOCKER,
            passed=passed,
            detail=detail,
            fix="Document install and first-run commands verbatim, so an agent can copy them without guessing.",
        )
    )


def check_tests(root: Path, report: Report) -> None:
    test_files = [
        p
        for p in _walk(root)
        if p.suffix in {".py", ".js", ".ts", ".go", ".rs", ".java", ".rb"}
        and (p.name.startswith("test_") or p.name.endswith(("_test.py", ".test.ts", ".test.js", ".spec.ts", ".spec.js")))
    ]
    in_tests_dir = (root / "tests").is_dir() or (root / "test").is_dir()
    passed = len(test_files) >= 1 or in_tests_dir
    report.add(
        Result(
            check_id="tests",
            title="Test suite exists",
            severity=Severity.HIGH,
            passed=passed,
            detail=f"{len(test_files)} test file(s) found." if passed else "No test files or tests/ directory.",
            fix="Add at least one runnable test — an agent with no test cannot verify its own change.",
        )
    )


def _fully_pinned_requirements(root: Path) -> List[str]:
    """Return requirements files in which every requirement pins an exact version.

    A plain ``requirements.txt`` is not a lockfile, but one where every line
    carries ``==`` is just as reproducible, so it counts.
    """
    pinned = []
    for path in sorted(root.glob("requirements*.txt")):
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        requirements = [
            line.strip()
            for line in lines
            if line.strip() and not line.strip().startswith(("#", "-"))
        ]
        if requirements and all("==" in line for line in requirements):
            pinned.append(path.name)
    return pinned


def check_lockfile(root: Path, report: Report) -> None:
    found = _exists_any(root, LOCKFILES) + _fully_pinned_requirements(root)
    report.add(
        Result(
            check_id="lockfile",
            title="Dependency versions are pinned",
            severity=Severity.HIGH,
            passed=bool(found),
            detail=(
                f"Found: {', '.join(found)}"
                if found
                else "No lockfile and no fully pinned requirements file — installs are not reproducible."
            ),
            fix="Commit the lockfile so the agent and CI resolve identical dependency versions.",
        )
    )


def check_ci(root: Path, report: Report) -> None:
    found = [p for p in CI_PATHS if (root / p).exists()]
    report.add(
        Result(
            check_id="ci",
            title="CI pipeline configured",
            severity=Severity.HIGH,
            passed=bool(found),
            detail=f"Found: {', '.join(found)}" if found else "No CI configuration.",
            fix="Add a workflow that runs the test command, so a broken change is caught without a human.",
        )
    )


def check_version_pin(root: Path, report: Report) -> None:
    found = _exists_any(root, VERSION_PIN_FILES)
    report.add(
        Result(
            check_id="toolchain-pin",
            title="Toolchain version pinned",
            severity=Severity.MEDIUM,
            passed=bool(found),
            detail=f"Found: {', '.join(found)}" if found else "No runtime version pin file.",
            fix="Pin the runtime version (.python-version, .nvmrc, rust-toolchain) to stop 'works on my machine'.",
        )
    )


def check_license(root: Path, report: Report) -> None:
    candidates = [p for p in root.glob("LICENSE*")] + [p for p in root.glob("COPYING*")]
    report.add(
        Result(
            check_id="license",
            title="License declared",
            severity=Severity.MEDIUM,
            passed=bool(candidates),
            detail=f"Found: {candidates[0].name}" if candidates else "No LICENSE file.",
            fix="Add a LICENSE file; without it nobody may legally reuse the code.",
        )
    )


def check_gitignore(root: Path, report: Report) -> None:
    path = root / ".gitignore"
    text = ""
    if path.exists():
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
    entries = [line.strip() for line in text.splitlines() if line.strip() and not line.startswith("#")]
    passed = len(entries) >= 3
    report.add(
        Result(
            check_id="gitignore",
            title=".gitignore excludes build artifacts",
            severity=Severity.MEDIUM,
            passed=passed,
            detail=f"{len(entries)} rule(s)." if passed else "Missing or nearly empty .gitignore.",
            fix="Ignore build output, caches and virtualenvs so an agent's noise never lands in a commit.",
        )
    )


def check_secrets(root: Path, report: Report) -> None:
    hits: List[str] = []
    scanned = 0
    for path in _walk(root):
        if path.suffix.lower() not in SCAN_SUFFIXES:
            continue
        try:
            if path.stat().st_size > MAX_SCAN_BYTES:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        scanned += 1
        for label, pattern in SECRET_PATTERNS:
            if pattern.search(text):
                hits.append(f"{path.relative_to(root)}: {label}")
    report.add(
        Result(
            check_id="secrets",
            title="No credentials committed",
            severity=Severity.BLOCKER,
            passed=not hits,
            detail=f"{len(hits)} potential secret(s): " + "; ".join(hits[:5]) if hits else f"{scanned} file(s) scanned, clean.",
            fix="Remove the credential, rotate it, and read it from an environment variable instead.",
        )
    )


CHECKS: List[Callable[[Path, Report], None]] = [
    check_agent_instructions,
    check_readme,
    check_tests,
    check_lockfile,
    check_ci,
    check_version_pin,
    check_license,
    check_gitignore,
    check_secrets,
]


def run_checks(root: Path) -> Report:
    """Run every registered check against ``root``."""
    report = Report(root=str(root))
    for check in CHECKS:
        check(root, report)
    return report
