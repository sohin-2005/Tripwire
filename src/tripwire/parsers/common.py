"""Turning a list of Steps into FileChanges and TestRuns, shared by every parser."""

from __future__ import annotations

from collections.abc import Callable

from tripwire.models import FileChange, Step, TestRun
from tripwire.parsers.testing import classify_test_output, is_test_command, is_test_path

SHELL_TOOLS = {"Bash", "bash"}

# Given a successful tool call and its result, return (path, before, after) for each file edit.
FileEdits = Callable[[Step, Step], list[tuple[str, str | None, str | None]]]


def extract_changes_and_tests(
    steps: list[Step], cwd: str | None, file_edits: FileEdits
) -> tuple[list[FileChange], list[TestRun]]:
    results = {s.tool_use_id: s for s in steps if s.kind == "tool_result"}
    changes: list[FileChange] = []
    test_runs: list[TestRun] = []
    for call in steps:
        result = results.get(call.tool_use_id) if call.kind == "tool_call" else None
        if result is None:
            continue
        if call.tool_name in SHELL_TOOLS:
            command = str((call.tool_input or {}).get("command", ""))
            if is_test_command(command):
                passed, summary = classify_test_output(result.text or "", result.is_error)
                test_runs.append(
                    TestRun(step_index=call.index, command=command, passed=passed, summary=summary)
                )
        elif not result.is_error:
            for path, before, after in file_edits(call, result):
                relative = relative_path(path, cwd)
                changes.append(
                    FileChange(
                        path=relative,
                        is_test=is_test_path(relative),
                        before=before,
                        after=after,
                        step_index=call.index,
                    )
                )
    return changes, test_runs


def relative_path(path: str, cwd: str | None) -> str:
    if cwd:
        prefix = cwd.rstrip("/") + "/"
        if path.startswith(prefix):
            return path[len(prefix):]
    return path
