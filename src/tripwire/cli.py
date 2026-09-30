"""Command line entry point: `tripwire parse ...`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tripwire.parsers.claude_code import iter_session_files, parse_claude_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tripwire")
    commands = parser.add_subparsers(dest="command", required=True)
    parse = commands.add_parser("parse", help="Convert Claude Code session logs to Run JSON.")
    parse.add_argument("path", type=Path, help="A session .jsonl file or a directory of them.")
    parse.add_argument("--out", type=Path, help="Write one Run per line to this file.")
    parse.add_argument(
        "--include-subagents", action="store_true", help="Also parse subagent logs."
    )
    args = parser.parse_args(argv)
    return _parse(args)


def _parse(args: argparse.Namespace) -> int:
    if args.path.is_file():
        files = [args.path]
    else:
        files = list(iter_session_files(args.path, args.include_subagents))
    runs = [parse_claude_code(f) for f in files]
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text("".join(run.model_dump_json() + "\n" for run in runs))
        print(f"wrote {len(runs)} runs to {args.out}", file=sys.stderr)
    elif args.path.is_file():
        print(runs[0].model_dump_json(indent=2))
    else:
        for run in runs:
            print(run.model_dump_json())
    return 0


if __name__ == "__main__":
    sys.exit(main())
