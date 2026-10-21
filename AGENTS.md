# AGENTS.md

Instructions for AI coding agents working in this repository.

## Setup

```bash
pip install -r requirements-dev.txt
```

The package itself has **no runtime dependencies**. Do not add one without a
written reason in the pull request.

## Commands

| Task | Command |
|---|---|
| Run all tests | `python -m unittest discover -s tests -v` |
| Run one test | `python -m unittest tests.test_checks.CheckTests.test_empty_repo_fails_blockers -v` |
| Audit this repo | `PYTHONPATH=src python -m codex_onboard .` |
| Install locally | `pip install -e .` |

Always run the full suite before reporting a change as complete. A change is not
done because the code looks right; it is done when the suite is green.

## Layout

```
src/codex_onboard/
  model.py       Result / Report dataclasses, severity weights, scoring
  checks.py      the nine checks; each appends one Result to the Report
  reporters.py   text and JSON rendering
  cli.py         argparse entry point
tests/
  test_checks.py everything, built on throwaway repos in temp dirs
```

## Conventions

- **Python 3.9 compatible.** No `match`, no `X | Y` type unions at runtime.
- **`from __future__ import annotations`** at the top of every module.
- **No third-party runtime dependencies.** Tests may use only the stdlib.
- **Checks are pure functions of the tree.** A check must never shell out, never
  hit the network, and never mutate the repository it is auditing — it runs on
  untrusted trees.
- **Every new check needs two tests**: one where it passes, one where it fails.
- **Severity is a claim about cost.** A blocker means "an agent cannot work
  reliably without this". Do not mark something a blocker to make the score
  move.

## Scoring contract

`Report.score` is `round(100 * earned / possible)`. When `possible == 0` the
score is `0` — an empty report must never look like a perfect repo. Tests pin
this behaviour; do not "fix" it.
