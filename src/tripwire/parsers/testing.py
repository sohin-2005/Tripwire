"""Heuristics for recognising test files, test-runner commands, and their results."""

from __future__ import annotations

import re
from pathlib import PurePosixPath

_TEST_DIRS = {"test", "tests", "__tests__"}
_TEST_NAME = re.compile(
    r"^(test_.*\.py|.*_test\.py|.*_test\.go|.*\.(test|spec)\.[jt]sx?|conftest\.py)$"
)

# Heredoc bodies (`<<'EOF' ... EOF`) are file contents or scripts, not commands.
_HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1[^\n]*\n.*?^\s*\2\s*$", re.DOTALL | re.MULTILINE)
_UNCLOSED_HEREDOC = re.compile(r"<<-?\s*(['\"]?)\w+\1.*", re.DOTALL)
_SEGMENT_SPLIT = re.compile(r"&&|\|\||;|\n")
_INSTALL = re.compile(r"\b(pip3?|uv|poetry|npm|yarn|pnpm|bun|brew)\s+(install|add|i)\b")
_TEST_COMMAND = re.compile(
    r"(^|[\s(/])("
    r"pytest|py\.test|python3? -m (pytest|unittest)|"
    r"(npm|yarn|pnpm|bun)( run)? test|vitest|jest|"
    r"go test|cargo test|make test|tox"
    r")\b"
)

_FAIL = [
    re.compile(p, re.MULTILINE)
    for p in (
        r"\b[1-9]\d* (failed|errors?|failing)\b",
        r"^FAILED\b",
        r"^FAIL\b",
        r"^--- FAIL",
        r"\bFAIL:",
        r"test result: FAILED",
    )
]
_PASS = [
    re.compile(p, re.MULTILINE)
    for p in (
        r"\b[1-9]\d* (passed|passing)\b",
        r"^OK\b",
        r"^ok\s",
        r"test result: ok",
    )
]


def is_test_path(path: str) -> bool:
    """True if the path looks like a test file (by directory or file name)."""
    p = PurePosixPath(path.replace("\\", "/"))
    if any(part in _TEST_DIRS for part in p.parts[:-1]):
        return True
    return bool(_TEST_NAME.match(p.name))


def is_test_command(command: str) -> bool:
    """True if any segment of a shell command runs a test runner (installs don't count)."""
    command = _UNCLOSED_HEREDOC.sub("", _HEREDOC.sub("", command))
    return any(
        _TEST_COMMAND.search(segment) and not _INSTALL.search(segment)
        for segment in _SEGMENT_SPLIT.split(command)
    )


def classify_test_output(output: str, is_error: bool | None) -> tuple[bool | None, str | None]:
    """Decide whether a test run passed. Returns (passed, summary line)."""
    summary = _summary_line(output)
    if is_error or any(p.search(output) for p in _FAIL):
        return False, summary
    if any(p.search(output) for p in _PASS):
        return True, summary
    return None, summary


def _summary_line(output: str) -> str | None:
    for line in reversed(output.splitlines()):
        stripped = line.strip(" =")
        if any(p.search(stripped) for p in _FAIL + _PASS):
            return stripped
    return None
