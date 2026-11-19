import importlib.util
import sys
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "eval_run", Path(__file__).resolve().parents[1] / "evals" / "run.py"
)
eval_run = importlib.util.module_from_spec(_spec)
sys.modules["eval_run"] = eval_run
_spec.loader.exec_module(eval_run)


def _case():
    return {
        "id": "demo",
        "prompt": "do it",
        "expect": {
            "must_mention": ["poteto-mode"],
            "must_not_mention": ["AskQuestion"],
            "gates": ["verify"],
        },
    }


def test_score_pass():
    ok, failures = eval_run.score(_case(), "Loading poteto-mode, will verify after.")
    assert ok
    assert failures == []


def test_score_missing_and_forbidden():
    ok, failures = eval_run.score(_case(), "AskQuestion first, no gates here.")
    assert not ok
    assert any("poteto-mode" in line for line in failures)
    assert any("AskQuestion" in line for line in failures)
    assert any("verify" in line for line in failures)


def test_load_golden():
    cases = eval_run.load_golden()
    assert cases
    for case in cases:
        assert case["id"] and case["prompt"] and case["expect"]


def test_build_argv_skill_arm_preloads_skill():
    argv = eval_run.build_argv({"prompt": "do it", "skill": "poteto-mode"}, "hermes", "skill")
    assert argv == ["hermes", "-z", "do it", "--skills", "poteto-mode"]


def test_build_argv_baseline_arm_omits_skill_flags():
    argv = eval_run.build_argv({"prompt": "do it", "skill": "poteto-mode"}, "hermes", "baseline")
    assert argv == ["hermes", "-z", "do it"]


def test_seed_home_skill_arm_registers_checkout_skills(tmp_path):
    active = tmp_path / "active"
    active.mkdir()
    (active / "config.yaml").write_text("model: x\n", encoding="utf-8")
    home = tmp_path / "home"

    eval_run.seed_home(home, active, register_checkout_skills=True)

    import yaml

    data = yaml.safe_load((home / "config.yaml").read_text(encoding="utf-8"))
    assert eval_run.CHECKOUT_SKILLS in data["skills"]["external_dirs"]


def test_seed_home_baseline_arm_prunes_checkout_skills_but_keeps_others(tmp_path):
    active = tmp_path / "active"
    active.mkdir()
    (active / "config.yaml").write_text(
        "skills:\n  external_dirs:\n"
        f"    - {eval_run.CHECKOUT_SKILLS}\n"
        "    - /opt/other-skills\n",
        encoding="utf-8",
    )
    home = tmp_path / "home"

    eval_run.seed_home(home, active, register_checkout_skills=False)

    import yaml

    data = yaml.safe_load((home / "config.yaml").read_text(encoding="utf-8"))
    dirs = data["skills"]["external_dirs"]
    assert eval_run.CHECKOUT_SKILLS not in dirs
    assert "/opt/other-skills" in dirs


def test_summarize_reports_pass_counts_and_handles_errors():
    records = [
        {"case": "a", "arm": "skill", "status": "pass"},
        {"case": "a", "arm": "skill", "status": "fail"},
        {"case": "a", "arm": "baseline", "status": "pass"},
        {"case": "a", "arm": "baseline", "status": "error"},
    ]

    rows = eval_run.summarize(records, eval_run.ARMS)

    assert len(rows) == 1
    assert rows[0]["skill"]["pass"] == 1
    assert rows[0]["skill"]["total"] == 2
    assert rows[0]["baseline"]["error"] == 1
    assert eval_run._rate(rows[0]["skill"]) == 50.0
    assert eval_run._rate(rows[0]["baseline"]) == 100.0


def test_seed_home_baseline_prunes_every_duplicate_checkout_entry(tmp_path):
    active = tmp_path / "active"
    active.mkdir()
    (active / "config.yaml").write_text(
        "skills:\n  external_dirs:\n"
        f"    - {eval_run.CHECKOUT_SKILLS}\n"
        f"    - {eval_run.CHECKOUT_SKILLS}\n"
        "    - /opt/other-skills\n",
        encoding="utf-8",
    )
    home = tmp_path / "home"

    eval_run.seed_home(home, active, register_checkout_skills=False)

    import yaml

    data = yaml.safe_load((home / "config.yaml").read_text(encoding="utf-8"))
    dirs = data["skills"]["external_dirs"]
    assert eval_run.CHECKOUT_SKILLS not in dirs
    assert dirs == ["/opt/other-skills"]


def test_rate_is_none_when_every_run_errored():
    cell = {"pass": 0, "total": 2, "error": 2}
    assert eval_run._rate(cell) is None


def test_print_summary_reports_the_skill_minus_baseline_delta(capsys):
    records = [
        {"case": "a", "arm": "skill", "status": "pass"},
        {"case": "a", "arm": "skill", "status": "pass"},
        {"case": "a", "arm": "baseline", "status": "pass"},
        {"case": "a", "arm": "baseline", "status": "fail"},
    ]

    eval_run._print_summary(eval_run.summarize(records, eval_run.ARMS), eval_run.ARMS, 2)

    out = capsys.readouterr().out
    assert "delta" in out
    assert "+50pp" in out
    assert "2/2" in out
    assert "1/2" in out


def test_print_summary_has_no_delta_column_for_a_single_arm(capsys):
    records = [{"case": "a", "arm": "skill", "status": "pass"}]

    eval_run._print_summary(eval_run.summarize(records, ("skill",)), ("skill",), 1)

    out = capsys.readouterr().out
    assert "delta" not in out
    assert "pp" not in out


def test_print_summary_prints_na_when_an_arm_has_no_scored_runs(capsys):
    records = [
        {"case": "a", "arm": "skill", "status": "pass"},
        {"case": "a", "arm": "baseline", "status": "error"},
    ]

    eval_run._print_summary(eval_run.summarize(records, eval_run.ARMS), eval_run.ARMS, 1)

    out = capsys.readouterr().out
    assert "n/a" in out
    assert "pp" not in out


def _fake_session_db(home, calls):
    """Write a minimal session DB into the isolated home a run_case created."""
    import json
    import sqlite3

    conn = sqlite3.connect(home / "state.db")
    conn.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY, started_at REAL)")
    conn.execute(
        "CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, "
        "role TEXT, content TEXT, tool_calls TEXT, tool_name TEXT, tool_call_id TEXT)"
    )
    conn.execute("INSERT INTO sessions VALUES ('s1', 1.0)")
    for index, (name, args, exit_code) in enumerate(calls):
        call_id = f"c{index}"
        payload = [{"call_id": call_id, "function": {"name": name, "arguments": json.dumps(args)}}]
        conn.execute(
            "INSERT INTO messages (session_id, role, tool_calls) VALUES ('s1','assistant',?)",
            (json.dumps(payload),),
        )
        if exit_code is not None:
            conn.execute(
                "INSERT INTO messages (session_id, role, content, tool_name, tool_call_id) "
                "VALUES ('s1','tool',?,'terminal',?)",
                (json.dumps({"exit_code": exit_code}), call_id),
            )
    conn.commit()
    conn.close()


def _stub_hermes(monkeypatch, tmp_path, calls, stdout):
    import subprocess

    active = tmp_path / "active"
    active.mkdir(exist_ok=True)
    (active / "config.yaml").write_text("model: x\n", encoding="utf-8")
    monkeypatch.setenv("HERMES_HOME", str(active))

    def fake_run(argv, **kwargs):
        _fake_session_db(Path(kwargs["env"]["HERMES_HOME"]), calls)
        return subprocess.CompletedProcess(argv, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(eval_run.subprocess, "run", fake_run)


def test_run_case_grades_a_clean_trajectory_end_to_end(monkeypatch, tmp_path):
    _stub_hermes(
        monkeypatch,
        tmp_path,
        [
            ("read_file", {"path": "a.py"}, None),
            ("patch", {"path": "a.py"}, None),
            ("terminal", {"command": "pytest -q"}, 0),
        ],
        "All tests pass — 1 passed.",
    )
    case = {
        "id": "demo",
        "prompt": "fix it",
        "skill": "s",
        "process": {"gates": ["read_before_write", "verify_before_claim"]},
    }

    status, failures, process = eval_run.run_case(case, "hermes", "skill")

    assert status == "pass", failures
    assert {p["gate"]: p["status"] for p in process} == {
        "read_before_write": "pass",
        "verify_before_claim": "pass",
    }


def test_run_case_fails_a_prose_only_claim_end_to_end(monkeypatch, tmp_path):
    _stub_hermes(
        monkeypatch,
        tmp_path,
        [("read_file", {"path": "a.py"}, None)],
        "All tests pass.",
    )
    case = {
        "id": "demo",
        "prompt": "fix it",
        "skill": "s",
        "process": {"gates": ["verify_before_claim"]},
    }

    status, failures, _process = eval_run.run_case(case, "hermes", "skill")

    assert status == "fail"
    assert any("verify_before_claim" in line for line in failures)


def test_score_accepts_alternates():
    case = _case()
    case["expect"]["must_mention"] = ["delegate|delegation|subagent"]
    ok, failures = eval_run.score(case, "Hand it to a subagent and verify.")
    assert ok, failures


def test_score_rejects_when_no_alternate_matches():
    case = _case()
    case["expect"]["must_mention"] = ["delegate|delegation"]
    ok, failures = eval_run.score(case, "I will do it myself, then verify.")
    assert not ok
    assert any("delegate|delegation" in line for line in failures)


def test_forbidden_accepts_alternates():
    case = _case()
    case["expect"]["must_not_mention"] = ["AskQuestion|AskUserQuestion"]
    ok, failures = eval_run.score(case, "Loading poteto-mode, will verify after. Then AskUserQuestion.")
    assert not ok
    assert any("forbidden present" in line for line in failures)


def test_routing_rubric_rejects_an_explicit_refusal_to_delegate():
    """`delegate` as an alternate must not let "I will not delegate" pass."""
    import json
    from pathlib import Path

    case = json.loads(
        (Path(__file__).resolve().parents[1] / "evals" / "golden" / "poteto-routing.json").read_text()
    )
    ok, _ = eval_run.score(
        case,
        "In poteto-mode I will not delegate; I will plan, then verify.",
    )
    assert not ok


def test_routing_rubric_contract():
    import json
    from pathlib import Path

    case = json.loads(
        (Path(__file__).resolve().parents[1] / "evals" / "golden" / "poteto-routing.json").read_text()
    )
    cases = [
        (
            "plain Task tool",
            "Loading poteto-mode. I will use the Task tool to delegate, with a plan and a verify step.",
            False,
        ),
        (
            "backticked Task tool",
            "Loading poteto-mode. I will use the `Task` tool to delegate, with a plan and a verify step.",
            False,
        ),
        (
            "backticked Task via",
            "Loading poteto-mode. I will delegate via `Task`, with a plan and a verify step.",
            False,
        ),
        (
            "backticked Task use",
            "Loading poteto-mode. I will use `Task` to delegate, with a plan and a verify step.",
            False,
        ),
        (
            "Task subagent",
            "Loading poteto-mode. I will use the Task subagent to delegate, with a plan and a verify step.",
            False,
        ),
        (
            "subagent_type",
            "Loading poteto-mode. I will delegate with subagent_type, with a plan and a verify step.",
            False,
        ),
        (
            "lowercase task code span",
            "In poteto-mode, I will plan the `task`, delegate the work, then verify it.",
            True,
        ),
        (
            "lowercase task prose",
            "In poteto-mode, I will plan the task, delegate the work, then verify it.",
            True,
        ),
        (
            "proper delegation",
            "Loading poteto-mode. I will delegate the refactor, plan first, then verify it.",
            True,
        ),
    ]
    for name, response, expected in cases:
        ok, failures = eval_run.score(case, response)
        assert ok is expected, f"{name}: expected {expected}, got {ok} ({failures})"


def test_build_env_is_isolated_and_marks_a_supervised_child(tmp_path):
    before = dict(__import__("os").environ)

    env = eval_run.build_env(tmp_path)

    assert env["HERMES_HOME"] == str(tmp_path)
    assert env["HERMES_SUPERVISED_CHILD"] == "1"
    assert dict(__import__("os").environ) == before


def test_tasks_filter_rejects_an_unknown_id(capsys):
    assert eval_run.main(["--tasks", "no-such-case"]) == 2
    assert "unknown task id" in capsys.readouterr().err


def test_tasks_filter_runs_only_the_named_case(monkeypatch):
    monkeypatch.setattr(eval_run, "preflight", lambda *a, **k: (True, "ok"))
    seen = []

    def fake_run(case, hermes="hermes", arm="skill", model="", timeout=300):
        seen.append(case["id"])
        return "pass", [], []

    monkeypatch.setattr(eval_run, "run_case", fake_run)

    assert eval_run.main(["--tasks", "poteto-routing"]) == 0
    assert seen == ["poteto-routing"]


def test_cleanup_removes_the_tree(tmp_path):
    target = tmp_path / "run"
    target.mkdir()
    (target / "f").write_text("x", encoding="utf-8")

    assert eval_run.cleanup(target) is True
    assert not target.exists()


def test_cleanup_retries_a_transient_failure(monkeypatch, tmp_path):
    import shutil

    target = tmp_path / "run"
    target.mkdir()
    calls = {"n": 0}
    real = shutil.rmtree

    def flaky(path, *a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError(66, "Directory not empty")
        return real(path, *a, **k)

    monkeypatch.setattr(eval_run.shutil, "rmtree", flaky)

    assert eval_run.cleanup(target, attempts=2) is True
    assert calls["n"] == 2


def test_cleanup_reports_giving_up(monkeypatch, tmp_path):

    def always_fail(path, *a, **k):
        raise OSError(66, "Directory not empty")

    monkeypatch.setattr(eval_run.shutil, "rmtree", always_fail)
    target = tmp_path / "run"
    target.mkdir()

    assert eval_run.cleanup(target, attempts=2) is False


def test_build_argv_pins_a_model_when_requested():
    argv = eval_run.build_argv({"prompt": "x", "skill": "s"}, "hermes", "baseline", "vendor/model:free")
    assert argv == ["hermes", "-z", "x", "-m", "vendor/model:free"]


def test_build_argv_omits_the_model_flag_by_default():
    argv = eval_run.build_argv({"prompt": "x", "skill": "s"}, "hermes", "skill", "")
    assert "-m" not in argv


def test_seed_home_copies_credentials_and_reuses_the_runtime(tmp_path):
    active = tmp_path / "active"
    active.mkdir()
    (active / "config.yaml").write_text("model: x\n", encoding="utf-8")
    (active / "auth.json").write_text("{}", encoding="utf-8")
    (active / "installs").mkdir()
    home = tmp_path / "home"

    eval_run.seed_home(home, active, register_checkout_skills=False)

    assert (home / "auth.json").is_file()
    assert (home / "installs").is_symlink()
    assert (home / "installs").resolve() == (active / "installs").resolve()


def test_seed_home_symlinks_an_absolute_runtime_for_a_relative_home(monkeypatch, tmp_path):

    active = tmp_path / "active"
    active.mkdir()
    (active / "config.yaml").write_text("model: x\n", encoding="utf-8")
    (active / "installs").mkdir()
    home = tmp_path / "home"
    monkeypatch.chdir(tmp_path)

    eval_run.seed_home(home, Path("active"), register_checkout_skills=False)

    assert (home / "installs").resolve() == (active / "installs").resolve()


def test_preflight_reports_a_missing_cli(monkeypatch):
    def fake_run(*a, **k):
        raise FileNotFoundError("hermes")

    monkeypatch.setattr(eval_run.subprocess, "run", fake_run)

    ok, detail = eval_run.preflight("hermes")

    assert not ok
    assert "--version failed" in detail


def test_preflight_reports_a_broken_cli(monkeypatch):
    import subprocess

    def fake_run(argv, **k):
        return subprocess.CompletedProcess(argv, 1, stdout="", stderr="Error: Gateway draining: update_paused")

    monkeypatch.setattr(eval_run.subprocess, "run", fake_run)

    ok, detail = eval_run.preflight("hermes")

    assert not ok
    assert "update_paused" in detail


def test_preflight_passes_and_returns_the_version(monkeypatch):
    import subprocess

    def fake_run(argv, **k):
        return subprocess.CompletedProcess(argv, 0, stdout="Hermes Agent v1.2.3\n", stderr="")

    monkeypatch.setattr(eval_run.subprocess, "run", fake_run)

    ok, detail = eval_run.preflight("hermes")

    assert ok
    assert detail.startswith("Hermes Agent")


def test_main_stops_before_cases_when_preflight_fails(monkeypatch, capsys):
    monkeypatch.setattr(eval_run, "preflight", lambda *a, **k: (False, "broken"))
    called = []
    monkeypatch.setattr(eval_run, "run_case", lambda *a, **k: called.append(1))

    assert eval_run.main(["--tasks", "poteto-routing"]) == 2
    assert called == []
    assert "preflight failed" in capsys.readouterr().err


def test_preflight_uses_a_throwaway_home(monkeypatch):
    import subprocess

    seen = {}

    def fake_run(argv, **k):
        seen["env"] = k.get("env") or {}
        return subprocess.CompletedProcess(argv, 0, stdout="Hermes Agent v1\n", stderr="")

    monkeypatch.setattr(eval_run.subprocess, "run", fake_run)

    ok, _ = eval_run.preflight("hermes")

    assert ok
    assert "pstack-preflight" in seen["env"]["HERMES_HOME"]
    assert seen["env"]["HERMES_SUPERVISED_CHILD"] == "1"


def test_preflight_timeout_is_configurable(monkeypatch):
    import subprocess

    seen = {}

    def fake_run(argv, **k):
        seen["timeout"] = k.get("timeout")
        return subprocess.CompletedProcess(argv, 0, stdout="v\n", stderr="")

    monkeypatch.setattr(eval_run.subprocess, "run", fake_run)

    eval_run.preflight("hermes", 120)

    assert seen["timeout"] == 120


def test_invalid_timeouts_are_rejected(capsys):
    assert eval_run.main(["--timeout", "0"]) == 2
    assert "--timeout" in capsys.readouterr().err


def test_json_out_records_every_run(monkeypatch, tmp_path):
    monkeypatch.setattr(eval_run, "preflight", lambda *a, **k: (True, "Hermes Agent v9"))

    def fake_run(case, hermes="hermes", arm="skill", model="", timeout=300):
        if arm == "skill":
            return "pass", [], [{"gate": "read_before_write", "status": "pass", "detail": "ok"}]
        return "fail", ["missing must_mention: x"], []

    monkeypatch.setattr(eval_run, "run_case", fake_run)
    out = tmp_path / "results" / "sweep.json"

    code = eval_run.main(
        ["--tasks", "poteto-routing", "--model", "m/x:free", "--arm", "both", "--reps", "2", "--json-out", str(out)]
    )

    import json

    payload = json.loads(out.read_text())
    assert code == 0  # baseline failures are data, not a gate failure
    assert payload["schema_version"] == "1"
    assert payload["hermes"] == "Hermes Agent v9"
    assert payload["model"] == "m/x:free"
    assert payload["arms"] == ["skill", "baseline"]
    assert payload["reps"] == 2
    assert len(payload["records"]) == 4
    assert {r["status"] for r in payload["records"] if r["arm"] == "skill"} == {"pass"}
    assert payload["summary"][0]["skill"]["pass"] == 2
    assert payload["summary"][0]["baseline"]["total"] == 2


def test_json_out_write_failure_is_an_error(monkeypatch, tmp_path):
    monkeypatch.setattr(eval_run, "preflight", lambda *a, **k: (True, "v"))
    monkeypatch.setattr(eval_run, "run_case", lambda *a, **k: ("pass", [], []))
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory", encoding="utf-8")

    code = eval_run.main(["--tasks", "poteto-routing", "--json-out", str(blocker / "sweep.json")])

    assert code == 2


def test_json_out_failure_keeps_the_previous_sweep(monkeypatch, tmp_path):
    monkeypatch.setattr(eval_run, "preflight", lambda *a, **k: (True, "v"))
    monkeypatch.setattr(eval_run, "run_case", lambda *a, **k: ("pass", [], []))
    target = tmp_path / "sweep.json"
    target.write_text("previous sweep", encoding="utf-8")

    def fail_replace(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(eval_run.os, "replace", fail_replace)

    assert eval_run.main(["--tasks", "poteto-routing", "--json-out", str(target)]) == 2
    assert target.read_text() == "previous sweep"
    assert not (tmp_path / "sweep.json.tmp").exists()
