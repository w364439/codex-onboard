"""Rendering: plain text for humans, JSON for automation."""

from __future__ import annotations

import json
from typing import Dict

from .model import Report

SEVERITY_TAG = {
    "blocker": "BLOCKER",
    "high": "HIGH",
    "medium": "MED",
    "low": "LOW",
}


def render_text(report: Report, color: bool = True) -> str:
    def paint(text: str, code: str) -> str:
        return f"\033[{code}m{text}\033[0m" if color else text

    lines = []
    lines.append(f"codex-onboard  {report.root}")
    lines.append("=" * 68)

    for result in report.results:
        mark = paint("PASS", "32") if result.passed else paint("FAIL", "31")
        tag = SEVERITY_TAG[result.severity.value].ljust(7)
        lines.append(f"[{mark}] {tag} {result.title}")
        lines.append(f"        {result.detail}")
        if not result.passed and result.fix:
            lines.append(f"        fix: {result.fix}")

    lines.append("=" * 68)
    lines.append(f"Score: {report.score}/100   Grade: {report.grade()}")

    failures = report.failures
    if failures:
        blockers = sum(1 for r in failures if r.severity.value == "blocker")
        lines.append(f"{len(failures)} unmet check(s), {blockers} of them blockers.")
    else:
        lines.append("All checks passed.")
    return "\n".join(lines)


def render_json(report: Report) -> str:
    payload: Dict[str, object] = {
        "root": report.root,
        "score": report.score,
        "grade": report.grade(),
        "passed": not report.failures,
        "checks": [
            {
                "id": r.check_id,
                "title": r.title,
                "severity": r.severity.value,
                "passed": r.passed,
                "detail": r.detail,
                "fix": r.fix,
            }
            for r in report.results
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)
