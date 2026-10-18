"""Summarise Inspect pilot logs and save them as Runs.

Usage: uv run --group bench python benchmark/pilot_report.py [LOG_DIR] [--out data/runs/pilot.jsonl]
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path

from tripwire.parsers.inspect_log import load_inspect_runs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("log_dir", nargs="?", default="data/inspect_logs/pilot")
    parser.add_argument("--out", default="data/runs/pilot.jsonl")
    args = parser.parse_args()

    runs = [run for f in sorted(Path(args.log_dir).glob("*.eval")) for run in load_inspect_runs(f)]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(run.model_dump_json() + "\n" for run in runs))

    by_split = defaultdict(list)
    for run in runs:
        by_split[(run.model, run.split)].append(run)
    print(f"{'model':28} {'split':12} {'runs':>4} {'passed':>6} {'cheated':>7} {'edited tests':>12} "
          f"{'errors':>6}")
    for (model, split), group in sorted(by_split.items()):
        labels = Counter(r.label for r in group)
        print(
            f"{model:28} {split:12} {len(group):>4} {sum(bool(r.tests_passed) for r in group):>6} "
            f"{labels['cheated']:>7} {sum(any(c.is_test for c in r.changes) for r in group):>12} "
            f"{sum(r.meta.get('sample_error', False) for r in group):>6}"
        )
    print(f"\n{len(runs)} runs written to {out}")


if __name__ == "__main__":
    main()
