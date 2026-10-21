"""Data model shared by checks and reporters."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, List


class Severity(str, Enum):
    """How much an unmet check costs you when an agent works in the repo."""

    BLOCKER = "blocker"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


SEVERITY_WEIGHT = {
    Severity.BLOCKER: 20,
    Severity.HIGH: 10,
    Severity.MEDIUM: 5,
    Severity.LOW: 2,
}


@dataclass(frozen=True)
class Result:
    """Outcome of a single check."""

    check_id: str
    title: str
    severity: Severity
    passed: bool
    detail: str
    fix: str = ""

    @property
    def weight(self) -> int:
        return SEVERITY_WEIGHT[self.severity]


@dataclass
class Report:
    """Aggregated results for one repository."""

    root: str
    results: List[Result] = field(default_factory=list)

    def add(self, result: Result) -> None:
        self.results.append(result)

    def extend(self, results: Iterable[Result]) -> None:
        self.results.extend(results)

    @property
    def earned(self) -> int:
        return sum(r.weight for r in self.results if r.passed)

    @property
    def possible(self) -> int:
        return sum(r.weight for r in self.results)

    @property
    def score(self) -> int:
        """Score out of 100. An empty report scores 0, not 100."""
        if self.possible == 0:
            return 0
        return round(100 * self.earned / self.possible)

    @property
    def failures(self) -> List[Result]:
        order = list(Severity)
        return sorted(
            (r for r in self.results if not r.passed),
            key=lambda r: order.index(r.severity),
        )

    def grade(self) -> str:
        score = self.score
        if score >= 90:
            return "A"
        if score >= 75:
            return "B"
        if score >= 60:
            return "C"
        if score >= 40:
            return "D"
        return "F"
