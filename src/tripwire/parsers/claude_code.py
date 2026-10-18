"""Parse a Claude Code session log into a Run.

Claude Code writes one JSONL file per session under ~/.claude/projects/<project>/.
User and assistant entries carry a `message` whose content is a string or a list of
blocks (text, thinking, tool_use, tool_result, image). Tool results sit in user
entries, and many carry a structured `toolUseResult`; for Edit and Write it includes
`originalFile`, the file's content before the change.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from tripwire.models import Run, Step, truncate
from tripwire.parsers.common import extract_changes_and_tests

# User messages Claude Code injects around slash commands and notifications.
_WRAPPER_PREFIXES = (
    "<local-command-caveat>",
    "<local-command-stdout>",
    "<command-name>",
    "<command-message>",
    "<task-notification>",
    "<system-reminder>",
)
_EDIT_TOOLS = {"Write", "Edit", "MultiEdit"}


def iter_session_files(root: str | Path, include_subagents: bool = False) -> Iterator[Path]:
    """Yield session logs under root, skipping subagent logs unless asked."""
    for path in sorted(Path(root).rglob("*.jsonl")):
        if include_subagents or "subagents" not in path.parts:
            yield path


def parse_claude_code(path: str | Path) -> Run:
    path = Path(path)
    entries, bad_lines = _read_entries(path)
    steps: list[Step] = []
    rich_results: dict[str, dict[str, Any]] = {}
    models: Counter[str] = Counter()
    cwd: str | None = None

    for entry in entries:
        if entry.get("isSidechain") or entry.get("type") not in ("user", "assistant"):
            continue
        cwd = cwd or entry.get("cwd")
        role = entry["type"]
        message = entry.get("message") or {}
        model = message.get("model")
        if role == "assistant" and model and not model.startswith("<"):
            models[model] += 1
        content = message.get("content")
        if isinstance(content, str):
            content = [{"type": "text", "text": content}]
        for block in content if isinstance(content, list) else []:
            step = _block_to_step(block, role, len(steps))
            if step is None:
                continue
            steps.append(step)
            if step.kind == "tool_result" and isinstance(entry.get("toolUseResult"), dict):
                rich_results[step.tool_use_id] = entry["toolUseResult"]

    known: dict[str, str] = {}  # path -> last known full content

    def file_edits(call: Step, result: Step) -> list[tuple[str, str | None, str | None]]:
        if call.tool_name not in _EDIT_TOOLS:
            return []
        extra = rich_results.get(call.tool_use_id, {})
        return _file_edits(call.tool_name, call.tool_input or {}, extra, known)

    changes, test_runs = extract_changes_and_tests(steps, cwd, file_edits)
    user_texts = [s.text for s in steps if s.role == "user" and s.kind == "text"]
    assistant_texts = [s.text for s in steps if s.role == "assistant" and s.kind == "text"]
    return Run(
        run_id=path.stem,
        source="claude_code",
        split="real",
        model=models.most_common(1)[0][0] if models else None,
        spec=user_texts[0] if user_texts else "",
        steps=steps,
        changes=changes,
        test_runs=test_runs,
        final_message=assistant_texts[-1] if assistant_texts else None,
        meta={"cwd": cwd, "path": str(path), "bad_lines": bad_lines},
    )


def _read_entries(path: Path) -> tuple[list[dict[str, Any]], int]:
    entries: list[dict[str, Any]] = []
    bad = 0
    with path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                bad += 1
                continue
            if isinstance(entry, dict):
                entries.append(entry)
            else:
                bad += 1
    return entries, bad


def _block_to_step(block: Any, role: str, index: int) -> Step | None:
    if not isinstance(block, dict):
        return None
    kind = block.get("type")
    if kind == "text":
        text = block.get("text") or ""
        if not text.strip() or (role == "user" and text.lstrip().startswith(_WRAPPER_PREFIXES)):
            return None
        return Step(index=index, role=role, kind="text", text=truncate(text))
    if kind == "tool_use":
        tool_input = block.get("input")
        return Step(
            index=index,
            role="assistant",
            kind="tool_call",
            tool_name=block.get("name"),
            tool_input=tool_input if isinstance(tool_input, dict) else {},
            tool_use_id=block.get("id"),
        )
    if kind == "tool_result":
        return Step(
            index=index,
            role="tool",
            kind="tool_result",
            text=truncate(_result_text(block.get("content"))),
            tool_use_id=block.get("tool_use_id"),
            is_error=bool(block.get("is_error")),
        )
    return None  # thinking, image, and anything new


def _result_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            b.get("text", "") if b.get("type") == "text" else f"[{b.get('type')}]"
            for b in content
            if isinstance(b, dict)
        )
    return ""


def _file_edits(
    tool: str, tool_input: dict[str, Any], extra: dict[str, Any], known: dict[str, str]
) -> list[tuple[str, str | None, str | None]]:
    path = str(tool_input.get("file_path") or extra.get("filePath") or "")
    if not path:
        return []
    if tool == "Write":
        after = str(tool_input.get("content", extra.get("content", "")))
        before = extra["originalFile"] if "originalFile" in extra else known.get(path)
        known[path] = after
        return [(path, before, after)]

    edits = [tool_input] if tool == "Edit" else list(tool_input.get("edits") or [])
    original = extra.get("originalFile") or known.get(path)
    if original is not None:
        current = original
        for edit in edits:
            old, new = str(edit.get("old_string", "")), str(edit.get("new_string", ""))
            if old not in current:
                break
            current = current.replace(old, new) if edit.get("replace_all") else current.replace(
                old, new, 1
            )
        else:
            known[path] = current
            return [(path, original, current)]
    known.pop(path, None)  # we no longer know the whole file
    return [(path, str(e.get("old_string", "")), str(e.get("new_string", ""))) for e in edits]
