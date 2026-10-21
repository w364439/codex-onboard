# codex-onboard

Audit a repository for **AI coding-agent readiness** before you hand it to Codex.

An agent that cannot build, test, or lint your project will guess — and guessing is
how you get confident-looking diffs that break the build. `codex-onboard` scores a
repository on the nine things an agent actually depends on, and tells you exactly
what to fix.

```
$ codex-onboard .
codex-onboard  /path/to/your/repo
====================================================================
[PASS] BLOCKER Agent instruction file present
        Found: AGENTS.md
[FAIL] HIGH    Test suite exists
        No test files or tests/ directory.
        fix: Add at least one runnable test — an agent with no test cannot verify its own change.
...
====================================================================
Score: 74/100   Grade: B
3 unmet check(s), 1 of them blockers.
```

## Why

Most "the AI broke my repo" stories are not model failures. They are missing
scaffolding: no test to run, no lockfile, no instruction file, so the agent
invents a command, invents a result, and reports success. This tool makes that
scaffolding visible and measurable in one command.

## Install

```bash
pip install -e .
```

Requires Python 3.9+. No runtime dependencies.

## Usage

```bash
codex-onboard                    # audit the current directory
codex-onboard path/to/repo       # audit a specific repo
codex-onboard --json             # machine-readable output
codex-onboard --min-score 80     # exit 1 when the score is below 80 (use in CI)
codex-onboard --no-color         # plain text, no ANSI escapes
```

Exit codes: `0` success, `1` score below `--min-score`, `2` path is not a directory.

## The nine checks

| Check | Severity | What it looks for |
|---|---|---|
| `agent-instructions` | blocker | `AGENTS.md`, `CLAUDE.md`, `.cursorrules` or `GEMINI.md` at the root |
| `readme` | blocker | A README of real length that contains an install/setup/usage section |
| `secrets` | blocker | Committed credentials (AWS keys, private key blocks, API keys, tokens) |
| `tests` | high | Test files or a `tests/` directory |
| `lockfile` | high | A lockfile, or a `requirements*.txt` where every line pins `==` |
| `ci` | high | GitHub Actions, GitLab CI, CircleCI, Azure Pipelines or Buildkite config |
| `toolchain-pin` | medium | `.python-version`, `.nvmrc`, `.tool-versions`, `rust-toolchain` |
| `license` | medium | `LICENSE` or `COPYING` |
| `gitignore` | medium | At least three ignore rules |

Scores are weighted by severity (blocker 20, high 10, medium 5, low 2) and
normalised to 100. An empty report scores **0**, never 100.

`node_modules`, `.venv`, `dist`, `target`, `vendor` and similar directories are
skipped, so vendored dependencies never produce false positives.

## Use it in CI

```yaml
- name: Agent readiness
  run: |
    pip install -e .
    codex-onboard . --min-score 80
```

## Development

```bash
pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

The suite builds throwaway repositories on disk, so every check is exercised
against real files rather than mocks.

## Limitations

- Heuristics, not proof. A passing score means the scaffolding exists, not that
  the tests are good.
- The secret scan is pattern-based and intentionally narrow; it complements a
  real secret scanner, it does not replace one.
- Single-repository only. Monorepos are scored as one tree.

## License

MIT
