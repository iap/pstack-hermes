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
        final="All tests pass now — 254 passed.",
    )

    result = trajectory.grade(
        {"gates": ["verify_before_claim"]},
        trajectory.load_tool_calls(db),
        "All tests pass now — 254 passed.",
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


def test_a_green_run_without_a_cited_result_is_unavailable(tmp_path):
    db = _db(tmp_path, [("terminal", {"command": "pytest -q"}, 0)], final="All tests pass.")

    result = trajectory.grade(
        {"gates": ["verify_before_claim"]},
        trajectory.load_tool_calls(db),
        "All tests pass.",
        _project(tmp_path),
    )[0]

    assert result["status"] == "unavailable"


def test_pytest_version_cannot_verify_a_claim(tmp_path):
    db = _db(tmp_path, [("terminal", {"command": "pytest --version"}, 0)], final="Tests pass.")

    result = trajectory.grade(
        {"gates": ["verify_before_claim"]},
        trajectory.load_tool_calls(db),
        "Tests pass.",
        _project(tmp_path),
    )[0]

    assert result["status"] == "fail"


def test_status_masking_continuation_is_unavailable(tmp_path):
    db = _db(tmp_path, [("terminal", {"command": "pytest -q || true"}, 0)], final="Tests pass.")

    result = trajectory.grade(
        {"gates": ["verify_before_claim"]},
        trajectory.load_tool_calls(db),
        "Tests pass.",
        _project(tmp_path),
    )[0]

    assert result["status"] == "unavailable"


def test_missing_exit_status_is_unavailable(tmp_path):
    db = _db(tmp_path, [("terminal", {"command": "pytest -q"}, None)], final="Tests pass.")

    result = trajectory.grade(
        {"gates": ["verify_before_claim"]},
        trajectory.load_tool_calls(db),
        "Tests pass.",
        _project(tmp_path),
    )[0]

    assert result["status"] == "unavailable"


def test_result_summary_claims_are_detected(tmp_path):
    db = _db(tmp_path, [], final="pytest: 254 passed in 94s")

    result = trajectory.grade(
        {"gates": ["verify_before_claim"]},
        trajectory.load_tool_calls(db),
        "pytest: 254 passed in 94s",
        _project(tmp_path),
    )[0]

    assert result["status"] == "fail"


def test_one_unproven_patch_path_blocks_a_pass(tmp_path):
    db = _db(
        tmp_path,
        [
            ("read_file", {"path": "a.py"}, None),
            ("patch", {"path": "a.py"}, None),
            ("patch", {"path": "b.py"}, None),
        ],
    )

    result = trajectory.grade(
        {"gates": ["read_before_write"]},
        trajectory.load_tool_calls(db),
        "done",
        _project(tmp_path),
    )[0]

    assert result["status"] == "not_applicable"


def test_database_with_no_session_is_not_an_empty_trajectory(tmp_path):
    path = tmp_path / "state.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY, started_at REAL)")
    conn.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY, session_id TEXT)")
    conn.commit()
    conn.close()

    assert trajectory.load_tool_calls(path) is None


def test_parser_reads_a_recorded_schema_fixture(tmp_path):
    """Real column layout from Hermes v0.22.5, sanitized rows.

    Synthetic DBs can drift from the product's schema without anyone noticing;
    this one is loaded from a checked-in dump of the real table definitions.
    """
    import sqlite3

    db = tmp_path / "recorded.db"
    sql = (Path(__file__).resolve().parent / "fixtures" / "session_record.sql").read_text(
        encoding="utf-8"
    )
    conn = sqlite3.connect(db)
    conn.executescript(sql)
    conn.commit()
    conn.close()

    calls = trajectory.load_tool_calls(db)

    assert [c["name"] for c in calls] == ["read_file", "patch", "terminal"]
    assert calls[2]["exit_code"] == 0
    result = trajectory.grade(
        {"gates": ["read_before_write", "verify_before_claim"]},
        calls,
        "All tests pass — 1 passed.",
        tmp_path,
    )
    assert {r["gate"]: r["status"] for r in result} == {
        "read_before_write": "pass",
        "verify_before_claim": "pass",
    }


def _no_banned_result(tmp_path, calls):
    return trajectory.grade(
        {"gates": ["no_banned_tool"]}, calls, "done", _project(tmp_path)
    )[0]


def test_no_banned_tool_accepts_delegate_task(tmp_path):
    db = _db(tmp_path, [("delegate_task", {"task": "review"}, None)])

    result = _no_banned_result(tmp_path, trajectory.load_tool_calls(db))

    assert result["status"] == "pass"


def test_no_banned_tool_fails_on_task_tool(tmp_path):
    db = _db(tmp_path, [("Task", {"task": "review"}, None)])

    result = _no_banned_result(tmp_path, trajectory.load_tool_calls(db))

    assert result["status"] == "fail"
    assert "Task" in result["detail"]


def test_no_banned_tool_fails_on_banned_argument(tmp_path):
    db = _db(tmp_path, [("delegate_task", {"subagent_type": "general"}, None)])

    result = _no_banned_result(tmp_path, trajectory.load_tool_calls(db))

    assert result["status"] == "fail"
    assert "subagent_type" in result["detail"]


def test_no_banned_tool_fails_without_delegate_task(tmp_path):
    db = _db(tmp_path, [("read_file", {"path": "a.py"}, None)])

    result = _no_banned_result(tmp_path, trajectory.load_tool_calls(db))

    assert result["status"] == "fail"
    assert "no delegate_task" in result["detail"]


def test_no_banned_tool_unavailable_without_a_record(tmp_path):
    result = _no_banned_result(tmp_path, None)

    assert result["status"] == "unavailable"


def _db_with_bad_calls(tmp_path, tool_calls_rows):
    path = tmp_path / "state.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY, started_at REAL)")
    conn.execute(
        "CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, "
        "role TEXT, content TEXT, tool_calls TEXT, tool_name TEXT, tool_call_id TEXT)"
    )
    conn.execute("INSERT INTO sessions VALUES ('s1', 1.0)")
    for row in tool_calls_rows:
        conn.execute(
            "INSERT INTO messages (session_id, role, tool_calls) VALUES ('s1', 'assistant', ?)",
            (row,),
        )
    conn.commit()
    conn.close()
    return path


def test_no_banned_tool_unavailable_on_unparseable_call_row(tmp_path):
    db = _db_with_bad_calls(
        tmp_path,
        [
            json.dumps([{"function": {"name": "delegate_task", "arguments": "{}"}}]),
            "not json",
        ],
    )

    result = _no_banned_result(tmp_path, trajectory.load_tool_calls(db))

    assert result["status"] == "unavailable"
    assert "unparseable" in result["detail"]


def test_no_banned_tool_unavailable_on_unparseable_arguments(tmp_path):
    db = _db_with_bad_calls(
        tmp_path,
        [json.dumps([{"function": {"name": "delegate_task", "arguments": "not json"}}])],
    )

    result = _no_banned_result(tmp_path, trajectory.load_tool_calls(db))

    assert result["status"] == "unavailable"


def test_no_banned_tool_unavailable_on_malformed_call_entries(tmp_path):
    valid = {"function": {"name": "delegate_task", "arguments": "{}"}}
    for malformed in [{}, 7]:
        db = _db_with_bad_calls(tmp_path, [json.dumps([valid, malformed])])

        result = _no_banned_result(tmp_path, trajectory.load_tool_calls(db))

        assert result["status"] == "unavailable"


def test_no_banned_tool_unavailable_on_non_object_arguments(tmp_path):
    db = _db_with_bad_calls(
        tmp_path,
        [json.dumps([{"function": {"name": "delegate_task", "arguments": '["subagent_type"]'}}])],
    )

    result = _no_banned_result(tmp_path, trajectory.load_tool_calls(db))

    assert result["status"] == "unavailable"


def test_grading_uses_root_session_not_a_later_delegate_child(tmp_path):
    db = tmp_path / "state.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE sessions (id TEXT PRIMARY KEY, parent_session_id TEXT, started_at REAL)"
    )
    conn.execute(
        "CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, "
        "role TEXT, content TEXT, tool_calls TEXT, tool_name TEXT, tool_call_id TEXT)"
    )
    conn.executemany(
        "INSERT INTO sessions VALUES (?, ?, ?)",
        [("parent", None, 1.0), ("child", "parent", 2.0)],
    )
    for session, name in [("parent", "delegate_task"), ("child", "Task")]:
        payload = [{"function": {"name": name, "arguments": "{}"}}]
        conn.execute(
            "INSERT INTO messages (session_id, role, tool_calls) VALUES (?, 'assistant', ?)",
            (session, json.dumps(payload)),
        )
    conn.commit()
    conn.close()

    calls = trajectory.load_tool_calls(db)

    assert [call["name"] for call in calls] == ["delegate_task"]
    assert _no_banned_result(tmp_path, calls)["status"] == "pass"
