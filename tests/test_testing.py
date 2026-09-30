import pytest

from tripwire.parsers.testing import classify_test_output, is_test_command, is_test_path


@pytest.mark.parametrize(
    "path, expected",
    [
        ("tests/test_dates.py", True),
        ("test_dates.py", True),
        ("pkg/dates_test.py", True),
        ("cmd/server_test.go", True),
        ("src/app.test.ts", True),
        ("src/app.spec.jsx", True),
        ("conftest.py", True),
        ("src/__tests__/app.js", True),
        ("src/dates.py", False),
        ("src/testing_utils.py", False),
        ("docs/test-plan.md", False),
    ],
)
def test_is_test_path(path, expected):
    assert is_test_path(path) is expected


@pytest.mark.parametrize(
    "command, expected",
    [
        ("pytest -q", True),
        ("cd /work && python -m pytest tests/", True),
        ("uv run pytest", True),
        (".venv/bin/pytest -x", True),
        ("python3 -m unittest discover", True),
        ("npm test", True),
        ("npm run test -- --watch=false", True),
        ("npx vitest run", True),
        ("go test ./...", True),
        ("cargo test", True),
        ("pip install pytest", False),
        ("uv pip install pytest-cov", False),
        ("uv add --dev pytest && ls", False),
        ("ls tests/", False),
        ("git status", False),
        ("python3 - <<'PY'\nimport pytest\nprint('edit')\nPY", False),
        ("cat >> tests/unit/test_a.py <<EOF\nimport pytest\ndef test_x(): pass\nEOF", False),
        ("python3 - <<'PY'\nprint('pytest')\nPY\npytest -q", True),
        ("cat > a.py <<\"EOF\"\nrun pytest later\n", False),
    ],
)
def test_is_test_command(command, expected):
    assert is_test_command(command) is expected


@pytest.mark.parametrize(
    "output, is_error, passed, summary",
    [
        ("F..\n1 failed, 2 passed in 0.12s", False, False, "1 failed, 2 passed in 0.12s"),
        ("...\n===== 3 passed in 0.02s =====", False, True, "3 passed in 0.02s"),
        ("Ran 3 tests in 0.001s\n\nOK", False, True, "OK"),
        ("Ran 3 tests\n\nFAILED (failures=1)", False, False, "FAILED (failures=1)"),
        ("ok  \texample.com/pkg\t0.01s", False, True, "ok  \texample.com/pkg\t0.01s"),
        ("Tests:       1 failed, 4 passed, 5 total", False, False,
         "Tests:       1 failed, 4 passed, 5 total"),
        ("Exit code 1\nsomething broke", True, False, None),
        ("collected 0 items", False, None, None),
    ],
)
def test_classify_test_output(output, is_error, passed, summary):
    assert classify_test_output(output, is_error) == (passed, summary)
