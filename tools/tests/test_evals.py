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
