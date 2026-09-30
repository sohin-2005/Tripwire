import json
from pathlib import Path

from tripwire.cli import main

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_single_file_prints_run_json(capsys):
    assert main(["parse", str(FIXTURES / "false_claim.jsonl")]) == 0
    run = json.loads(capsys.readouterr().out)
    assert run["run_id"] == "false_claim"
    assert run["test_runs"][0]["passed"] is False


def test_parse_directory_writes_jsonl(tmp_path):
    out = tmp_path / "runs.jsonl"
    assert main(["parse", str(FIXTURES), "--out", str(out)]) == 0
    ids = sorted(json.loads(line)["run_id"] for line in out.read_text().splitlines())
    assert ids == ["false_claim", "write_and_pass"]
