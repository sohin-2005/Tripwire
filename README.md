# Tripwire

**Can a cheap detector catch coding agents that fake success, on a benchmark and in real sessions?**

When a coding agent can't solve a task, it sometimes makes the check pass instead of the code
correct: weakening a test, skipping it, hardcoding the answer, or claiming success after a failing
run. Tripwire builds detectors for this, evaluates them on
[ImpossibleBench](https://github.com/safety-research/impossiblebench) and on real Claude Code
sessions, and ships the best one as a tool.

Status: 🚧 ongoing — sub-project 1 of 6 (log parsing foundation) done.

## Try it

    uv sync
    uv run tripwire parse tests/fixtures/false_claim.jsonl
    uv run python scripts/survey_sessions.py   # counts over your own ~/.claude/projects

## Layout

- `src/tripwire/models.py` — the standard `Run` format every parser produces
- `src/tripwire/parsers/` — log parsers (Claude Code today, Inspect next)
- `docs/superpowers/` — design specs and implementation plans
