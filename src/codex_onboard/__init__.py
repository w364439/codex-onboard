"""codex-onboard — audit a repository for AI coding-agent readiness."""

from .checks import CHECKS, run_checks
from .model import Report, Result, Severity

__version__ = "0.1.0"

__all__ = ["CHECKS", "Report", "Result", "Severity", "run_checks", "__version__"]
