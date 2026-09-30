"""Parse every local Claude Code session and print counts (never message content).

Usage: uv run python scripts/survey_sessions.py [ROOT]   (default ~/.claude/projects)
"""

from __future__ import annotations

import sys
from pathlib import Path

from tripwire.parsers.claude_code import iter_session_files, parse_claude_code

HEADER = ("project", "session", "steps", "calls", "changes", "test_chg", "tests", "failed", "bad")


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / ".claude" / "projects"
    rows, failures = [], []
    for path in iter_session_files(root):
        try:
            run = parse_claude_code(path)
        except Exception as exc:  # noqa: BLE001 — the survey's job is to find these
            failures.append((path, exc))
            continue
        rows.append(
            (
                path.parent.name[-30:],
                run.run_id[:8],
                len(run.steps),
                sum(s.kind == "tool_call" for s in run.steps),
                len(run.changes),
                sum(c.is_test for c in run.changes),
                len(run.test_runs),
                sum(t.passed is False for t in run.test_runs),
                run.meta["bad_lines"],
            )
        )
    widths = [max(len(str(x)) for x in col) for col in zip(HEADER, *rows)]
    for row in [HEADER, *rows]:
        print("  ".join(str(x).ljust(w) for x, w in zip(row, widths)))
    totals = [sum(col) for col in list(zip(*rows))[2:]] if rows else []
    print(f"\n{len(rows)} sessions parsed, {len(failures)} failed. Totals {dict(zip(HEADER[2:], totals))}")
    for path, exc in failures:
        print(f"FAILED {path}: {exc!r}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
