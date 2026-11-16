"""Trajectory graders: prove the evidence rules without a live agent (#213).

Every case builds a synthetic session database. The point is the boundary:
missing or ambiguous evidence must never become a pass.
"""

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evals"))

import trajectory  # noqa: E402


def _db(tmp_path, calls, final="done"):
    """Create a session DB. calls: list of (name, args, exit_code|None)."""
    path = tmp_path / "state.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY, started_at REAL)")
    conn.execute(
        "CREATE TABLE messages ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, role TEXT, "
        "content TEXT, tool_calls TEXT, tool_name TEXT, tool_call_id TEXT)"
    )
    conn.execute("INSERT INTO sessions VALUES ('s1', 1.0)")
    for index, (name, args, exit_code) in enumerate(calls):
        call_id = f"c{index}"
        payload = [
            {
                "id": call_id,
                "call_id": call_id,
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(args)},
            }
        ]
        conn.execute(
            "INSERT INTO messages (session_id, role, tool_calls) VALUES (?, 'assistant', ?)",
            ("s1", json.dumps(payload)),
        )
        if exit_code is not None:
            conn.execute(
                "INSERT INTO messages (session_id, role, content, tool_name, tool_call_id) "
                "VALUES (?, 'tool', ?, 'terminal', ?)",
                ("s1", json.dumps({"output": "", "exit_code": exit_code}), call_id),
            )
    conn.execute(
        "INSERT INTO messages (session_id, role, content) VALUES ('s1', 'assistant', ?)",
        (final,),
    )
    conn.commit()
    conn.close()
    return path


def _project(tmp_path):
    project = tmp_path / "project"
    project.mkdir(exist_ok=True)
    return project


def test_load_tool_calls_keeps_order_and_exit_codes(tmp_path):
    db = _db(
        tmp_path,
        [("read_file", {"path": "a.py"}, None), ("terminal", {"command": "pytest -q"}, 0)],
    )

    calls = trajectory.load_tool_calls(db)

    assert [c["name"] for c in calls] == ["read_file", "terminal"]
    assert calls[1]["exit_code"] == 0


def test_missing_db_is_not_an_empty_pass(tmp_path):
    assert trajectory.load_tool_calls(tmp_path / "absent.db") is None


def test_read_before_write_passes_only_for_the_same_path(tmp_path):
    db = _db(
        tmp_path,
        [("read_file", {"path": "a.py"}, None), ("patch", {"path": "a.py"}, None)],
    )

    result = trajectory.grade(
        {"gates": ["read_before_write"]},
        trajectory.load_tool_calls(db),
        "done",
        _project(tmp_path),
    )[0]

    assert result["status"] == "pass"


def test_a_patch_with_no_read_at_all_is_unknown_not_failed(tmp_path):
    """The agent may have read it with `cat`; absence of read_file is not proof."""
    db = _db(tmp_path, [("patch", {"path": "a.py"}, None)])

    result = trajectory.grade(
        {"gates": ["read_before_write"]},
        trajectory.load_tool_calls(db),
        "done",
        _project(tmp_path),
    )[0]

    assert result["status"] == "not_applicable"


def test_read_before_write_normalises_relative_and_absolute_paths(tmp_path):
    project = _project(tmp_path)
    db = _db(
        tmp_path,
        [
            ("read_file", {"path": "a.py"}, None),
            ("patch", {"path": str(project / "a.py")}, None),
        ],
    )

    result = trajectory.grade(
        {"gates": ["read_before_write"]}, trajectory.load_tool_calls(db), "done", project
    )[0]

    assert result["status"] == "pass"


def test_read_before_write_is_not_applicable_without_a_write(tmp_path):
    db = _db(tmp_path, [("read_file", {"path": "a.py"}, None)])

    result = trajectory.grade(
        {"gates": ["read_before_write"]},
        trajectory.load_tool_calls(db),
        "done",
        _project(tmp_path),
    )[0]

    assert result["status"] == "not_applicable"


def test_terminal_writes_never_produce_a_pass(tmp_path):
    db = _db(
        tmp_path,
        [
            ("read_file", {"path": "a.py"}, None),
            ("terminal", {"command": "printf x > a.py"}, 0),
        ],
    )

    result = trajectory.grade(
        {"gates": ["read_before_write"]},
        trajectory.load_tool_calls(db),
        "done",
        _project(tmp_path),
    )[0]

    assert result["status"] == "not_applicable"


def test_verify_before_claim_passes_on_a_green_test_run(tmp_path):
    db = _db(
        tmp_path,
        [("terminal", {"command": "uv run --frozen pytest -q"}, 0)],
        final="All tests pass now.",
    )

    result = trajectory.grade(
        {"gates": ["verify_before_claim"]},
        trajectory.load_tool_calls(db),
        "All tests pass now.",
        _project(tmp_path),
    )[0]

    assert result["status"] == "pass"


def test_verify_before_claim_fails_when_the_test_run_failed(tmp_path):
    db = _db(
        tmp_path,
        [("terminal", {"command": "pytest -q"}, 1)],
        final="Tests pass.",
    )

    result = trajectory.grade(
        {"gates": ["verify_before_claim"]},
        trajectory.load_tool_calls(db),
        "Tests pass.",
        _project(tmp_path),
    )[0]

    assert result["status"] == "fail"


def test_verify_before_claim_fails_with_no_test_command(tmp_path):
    db = _db(tmp_path, [("read_file", {"path": "a.py"}, None)], final="All tests pass.")

    result = trajectory.grade(
        {"gates": ["verify_before_claim"]},
        trajectory.load_tool_calls(db),
        "All tests pass.",
        _project(tmp_path),
    )[0]

    assert result["status"] == "fail"


def test_generic_done_language_does_not_trigger_the_verify_gate(tmp_path):
    db = _db(tmp_path, [], final="Done — fixed the issue.")

    result = trajectory.grade(
        {"gates": ["verify_before_claim"]},
        trajectory.load_tool_calls(db),
        "Done — fixed the issue.",
        _project(tmp_path),
    )[0]

    assert result["status"] == "not_applicable"


def test_unknown_gate_is_unavailable(tmp_path):
    result = trajectory.grade({"gates": ["vibes"]}, [], "done", tmp_path)[0]
    assert result["status"] == "unavailable"


def test_test_command_detection_is_not_fooled_by_filenames():
    assert not trajectory._is_test_command("cat pytest.ini")
    assert not trajectory._is_test_command("grep pytest README.md")
    assert not trajectory._is_test_command("echo 'pytest -q' >> notes.txt")


def test_test_command_detection_accepts_real_invocations():
    assert trajectory._is_test_command("uv run --frozen pytest -q")
    assert trajectory._is_test_command("cd repo && pytest -q")
    assert trajectory._is_test_command("npm test")
    assert trajectory._is_test_command("python -m pytest tools/tests")


def test_collection_only_and_help_do_not_count_as_a_verification():
    assert not trajectory._is_test_command("pytest --collect-only")
    assert not trajectory._is_test_command("pytest --co")
    assert not trajectory._is_test_command("pytest --help")


def test_patch_with_a_path_is_graded_like_a_write(tmp_path):
    db = _db(
        tmp_path,
        [("read_file", {"path": "a.py"}, None), ("patch", {"path": "a.py"}, None)],
    )

    result = trajectory.grade(
        {"gates": ["read_before_write"]},
        trajectory.load_tool_calls(db),
        "done",
        _project(tmp_path),
    )[0]

    assert result["status"] == "pass"


def test_v4a_patch_without_a_path_is_unavailable(tmp_path):
    db = _db(
        tmp_path,
        [("read_file", {"path": "a.py"}, None), ("patch", {"mode": "v4a"}, None)],
    )

    result = trajectory.grade(
        {"gates": ["read_before_write"]},
        trajectory.load_tool_calls(db),
        "done",
        _project(tmp_path),
    )[0]

    assert result["status"] == "unavailable"


def test_reading_after_patching_fails(tmp_path):
    db = _db(
        tmp_path,
        [("patch", {"path": "a.py"}, None), ("read_file", {"path": "a.py"}, None)],
    )

    result = trajectory.grade(
        {"gates": ["read_before_write"]},
        trajectory.load_tool_calls(db),
        "done",
        _project(tmp_path),
    )[0]

    assert result["status"] == "fail"


def test_readonly_terminal_commands_do_not_block_grading(tmp_path):
    db = _db(
        tmp_path,
        [
            ("read_file", {"path": "a.py"}, None),
            ("terminal", {"command": "ls -la 2>&1"}, 0),
            ("patch", {"path": "a.py"}, None),
        ],
    )

    result = trajectory.grade(
        {"gates": ["read_before_write"]},
        trajectory.load_tool_calls(db),
        "done",
        _project(tmp_path),
    )[0]

    assert result["status"] == "pass"


def test_terminal_only_writes_are_not_graded(tmp_path):
    """A shell redirect names no path argument; the gate stays silent."""
    db = _db(
        tmp_path,
        [
            ("read_file", {"path": "a.py"}, None),
            ("terminal", {"command": "echo x > a.py"}, 0),
        ],
    )

    result = trajectory.grade(
        {"gates": ["read_before_write"]},
        trajectory.load_tool_calls(db),
        "done",
        _project(tmp_path),
    )[0]

    assert result["status"] == "not_applicable"


def test_write_file_without_a_read_is_not_a_failure(tmp_path):
    """Creating a file needs no prior read; overwriting is indistinguishable.

    Failing here would be a false positive — observed on a real session that
    wrote a brand-new report JSON.
    """
    db = _db(tmp_path, [("write_file", {"path": "new-report.json"}, None)])

    result = trajectory.grade(
        {"gates": ["read_before_write"]},
        trajectory.load_tool_calls(db),
        "done",
        _project(tmp_path),
    )[0]

    assert result["status"] == "not_applicable"
