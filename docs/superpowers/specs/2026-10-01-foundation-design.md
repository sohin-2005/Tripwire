# Sub-project 1: Foundation — Design

Date: 2026-10-01 · Status: approved in chat, awaiting written review

## What this is (plain language)

Tripwire checks whether a coding agent cheated to make tests pass. Before any
checker can exist, we need a **translator**: something that reads an agent's log
file and turns it into one standard format, so every later piece (labeling,
detectors, evaluation, the shipped tool) works on the same data no matter where
the log came from.

This sub-project builds that translator for **Claude Code logs**, plus the
standard format itself and the repo it lives in.

## Goal and success criteria

- A Python package `tripwire` (PyPI name `agent-tripwire`) with a standard `Run` format.
- `tripwire parse <session.jsonl>` prints a `Run` as JSON.
- Success =
  1. Unit tests pass on small hand-made fixture logs.
  2. The parser runs over **all local main sessions** in `~/.claude/projects` without crashing,
     and a summary script reports steps / file changes / test runs per session.
  3. For a fixture where the agent says "all tests pass" after a failing test run,
     the `Run` shows the failing `TestRun` and the claim in `final_message` — the raw
     material the T7 (false claim) detector will need.

## Out of scope (later sub-projects)

- **Inspect (ImpossibleBench) parser.** We have no Inspect logs yet; guessing their
  format would be wasted work. It is the first task of sub-project 2, written against
  real pilot logs, producing the same `Run` model.
- Detectors, labels, splits, LLM calls, MCP server, hooks, PyPI publishing.

## Standard format (`src/tripwire/models.py`, Pydantic v2)

- `Step` — one thing that happened: `index`, `role` (user/assistant/tool),
  `kind` (text/tool_call/tool_result), `text` (truncated to 10,000 chars),
  `tool_name`, `tool_input`, `tool_use_id`, `is_error`.
- `FileChange` — one file edit: `path`, `is_test`, `before`, `after`
  (`None` before = created, `None` after = deleted), `step_index`.
- `TestRun` — one time tests were run: `step_index`, `command`,
  `passed` (`True`/`False`/`None` = unknown), `summary` (e.g. "3 failed, 12 passed").
- `Run` — the whole session: `run_id`, `source` (inspect/claude_code),
  `problem_id`, `split` (original/oneoff/conflicting/custom/real), `model`, `spec`,
  `steps`, `changes`, `test_runs`, `tests_passed`, `final_message`,
  plus optional labels `label`, `cheat_types`, `label_source`, and `meta`
  (source-specific extras: `cwd`, `path`, `bad_lines`).
  - `Run.diff()` builds a readable unified diff from `changes`.
  - `Run.without_labels()` returns a copy with labels cleared; detectors only ever
    receive this, so they can't accidentally see the answer.
- Storage: JSONL, one run per line, under `data/runs/` (git-ignored).

## Claude Code parser (`src/tripwire/parsers/claude_code.py`)

Input: one session `.jsonl` file. Each line is an entry with `type`
(`user`/`assistant`/`system`/`summary`/…) and usually a `message` whose `content`
is a string or a list of blocks (`text`, `thinking`, `tool_use`, `tool_result`).

Rules:
- Skip entries that aren't user/assistant messages, `thinking` blocks, and
  sidechain (subagent) entries (`isSidechain: true`) — v1 looks at the main agent only.
- `spec` = the first user text message that isn't a tool result or a
  command/caveat wrapper.
- `final_message` = the last assistant text block.
- `model` = the `message.model` of assistant entries (most common value).
- `run_id` = session id; `source` = `claude_code`; `split` = `real`.
- **File changes** come from tool calls, matched to their results by `tool_use_id`,
  kept only when the result is not an error:
  - `Write` → `after` = content; `before` = `None` unless the same file was seen earlier
    in the session (then the last known content).
  - `Edit` / `MultiEdit` → when the result's `toolUseResult.originalFile` (or an earlier
    known version of the file) is available and contains the old string, `before` is the
    whole file and `after` is it with the edit applied. Otherwise (about half of local
    edits) `before`/`after` are the edited snippets — still enough to spot a removed
    assertion or an added `skip`.
  - Write's `before` comes from `toolUseResult.originalFile` when present.
- Session files under a `subagents/` directory are skipped by default (local survey:
  16 main sessions, 35 subagent logs).
  - `NotebookEdit` and others: ignored in v1.
- **Test runs**: a `Bash` call whose command matches a test runner
  (`pytest`, `python -m pytest`, `python -m unittest`, `npm test`, `npm run test`,
  `yarn test`, `pnpm test`, `vitest`, `jest`, `go test`, `cargo test`, `make test`, `tox`).
  `passed`: `False` if the result is an error or the output has a failure summary
  (`N failed`, `FAILED`, `Error`), `True` if it has a success summary (`N passed`,
  `OK`, `ok`) and no failures, else `None`. `summary` = the matched summary line.
- **Test file detection** (`is_test`): path under a `test`/`tests`/`__tests__`
  directory, or named `test_*.py`, `*_test.py`, `*_test.go`, `*.test.[jt]sx?`,
  `*.spec.[jt]sx?`, `conftest.py`.
- Malformed lines are skipped and counted, never crash the parse.

## Known gaps (found by the local survey)

- **File edits made through Bash are not in `changes`.** Local sessions often edit
  files — including tests — with `python3 - <<'PY' ...` scripts or `cat >> tests/... <<EOF`.
  They appear only as Bash steps. The rules detector (sub-project 4) must flag Bash
  commands that write to test paths; a cheat could otherwise hide here.
- Test-command detection strips heredoc bodies first, so a script that merely mentions
  `pytest` isn't counted as a test run.

## Command line (`src/tripwire/cli.py`, standard-library argparse)

- `tripwire parse <file>` → prints the `Run` as JSON.
- `tripwire parse <dir> --out runs.jsonl` → parses every `.jsonl` under the dir.
- `scripts/survey_sessions.py` → runs the parser over `~/.claude/projects` and prints
  a table of counts per session (no message content), for success criterion 2.

## Privacy

Real session logs never go into the repo. Test fixtures are **hand-written**
small logs that mimic the real format. `data/` is git-ignored.

## Repo layout after this sub-project

```
TripWire/
├── pyproject.toml          uv project, package agent-tripwire, Python >=3.11
├── README.md               the question + status
├── .gitignore              data/, .venv, caches
├── src/tripwire/
│   ├── __init__.py
│   ├── models.py
│   ├── cli.py
│   └── parsers/
│       ├── __init__.py
│       ├── claude_code.py
│       └── testing.py      test-command + test-file detection helpers
├── scripts/survey_sessions.py
├── tests/
│   ├── fixtures/           hand-made .jsonl logs
│   ├── test_models.py
│   ├── test_testing.py
│   └── test_claude_code_parser.py
└── docs/superpowers/specs/
```

## Tooling

uv for env and deps; dependencies: `pydantic`. Dev: `pytest`, `ruff`.
Written test-first: each parser rule gets a failing test before the code.
