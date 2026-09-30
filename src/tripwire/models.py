"""The standard run format: every parser produces a Run, every detector consumes one."""

from __future__ import annotations

import difflib
from typing import Any, Literal

from pydantic import BaseModel, Field

Role = Literal["user", "assistant", "tool"]
StepKind = Literal["text", "tool_call", "tool_result"]
Source = Literal["inspect", "claude_code"]
Split = Literal["original", "oneoff", "conflicting", "custom", "real"]
Label = Literal["honest_success", "honest_failure", "cheated", "unclear"]
CheatType = Literal["T1", "T2", "T3", "T4", "T5", "T6", "T7"]

MAX_TEXT = 10_000


def truncate(text: str | None, limit: int = MAX_TEXT) -> str | None:
    """Shorten long text, keeping the head and the tail (test summaries live at the end)."""
    if text is None or len(text) <= limit:
        return text
    half = limit // 2
    return f"{text[:half]}\n...[{len(text) - limit} chars truncated]...\n{text[-half:]}"


class Step(BaseModel):
    """One thing that happened in a session: a message, a tool call, or a tool result."""

    index: int
    role: Role
    kind: StepKind
    text: str | None = None
    tool_name: str | None = None
    tool_input: dict[str, Any] | None = None
    tool_use_id: str | None = None
    is_error: bool | None = None


class FileChange(BaseModel):
    """One file edit. before=None means the file was created; after=None means deleted."""

    path: str
    is_test: bool
    before: str | None
    after: str | None
    step_index: int


class TestRun(BaseModel):
    """One time the agent ran tests. passed=None means the output didn't say."""

    __test__ = False  # not a pytest test class

    step_index: int
    command: str
    passed: bool | None
    summary: str | None = None


class Run(BaseModel):
    """A whole agent session in the standard format."""

    run_id: str
    source: Source
    problem_id: str | None = None
    split: Split
    model: str | None = None
    spec: str
    steps: list[Step] = Field(default_factory=list)
    changes: list[FileChange] = Field(default_factory=list)
    test_runs: list[TestRun] = Field(default_factory=list)
    tests_passed: bool | None = None
    final_message: str | None = None
    label: Label | None = None
    cheat_types: list[CheatType] = Field(default_factory=list)
    label_source: Literal["automatic", "human"] | None = None
    meta: dict[str, Any] = Field(default_factory=dict)

    def diff(self) -> str:
        """A unified diff of every change, for LLM judges and humans."""
        parts: list[str] = []
        for change in self.changes:
            parts.extend(
                difflib.unified_diff(
                    _lines(change.before),
                    _lines(change.after),
                    fromfile="/dev/null" if change.before is None else f"a/{change.path}",
                    tofile="/dev/null" if change.after is None else f"b/{change.path}",
                )
            )
        return "".join(parts)

    def without_labels(self) -> Run:
        """A copy with the answer removed. Detectors only ever see this."""
        return self.model_copy(
            update={"label": None, "cheat_types": [], "label_source": None}, deep=True
        )


def _lines(text: str | None) -> list[str]:
    return [
        line if line.endswith("\n") else line + "\n"
        for line in (text or "").splitlines(keepends=True)
    ]
