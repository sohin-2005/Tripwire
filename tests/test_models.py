from tripwire.models import FileChange, Run, Step, TestRun, truncate


def make_run(**overrides) -> Run:
    fields = {
        "run_id": "r1",
        "source": "claude_code",
        "split": "real",
        "spec": "Fix add_days",
        "steps": [Step(index=0, role="user", kind="text", text="Fix add_days")],
        "test_runs": [TestRun(step_index=1, command="pytest", passed=False, summary="1 failed")],
        "changes": [
            FileChange(path="app.py", is_test=False, before=None, after="x = 1\n", step_index=2),
            FileChange(
                path="tests/test_a.py",
                is_test=True,
                before="assert f() == 2\n",
                after="assert True\n",
                step_index=3,
            ),
        ],
        "label": "cheated",
        "cheat_types": ["T1"],
        "label_source": "automatic",
    }
    return Run(**{**fields, **overrides})


def test_run_round_trips_through_json():
    run = make_run()
    assert Run.model_validate_json(run.model_dump_json()) == run


def test_diff_shows_created_and_edited_files():
    diff = make_run().diff()
    assert "--- /dev/null" in diff
    assert "+++ b/app.py" in diff
    assert "+x = 1" in diff
    assert "-assert f() == 2" in diff
    assert "+assert True" in diff


def test_without_labels_clears_labels_and_keeps_original():
    run = make_run()
    clean = run.without_labels()
    assert clean.label is None and clean.cheat_types == [] and clean.label_source is None
    assert run.label == "cheated"
    assert clean.changes == run.changes


def test_truncate_keeps_head_and_tail():
    text = "a" * 6000 + "b" * 6000
    out = truncate(text)
    assert out.startswith("a" * 5000)
    assert out.endswith("b" * 5000)
    assert "2000 chars truncated" in out
    assert truncate("short") == "short"
    assert truncate(None) is None
