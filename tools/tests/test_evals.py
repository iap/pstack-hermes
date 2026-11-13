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

def test_score_accepts_alternates():
    case = _case()
    case["expect"]["must_mention"] = ["delegate|delegation|subagent"]
    ok, failures = eval_run.score(case, "Hand it to a subagent and verify.")
    assert ok, failures


def test_score_rejects_when_no_alternate_matches():
    case = _case()
    case["expect"]["must_mention"] = ["delegate|subagent"]
    ok, failures = eval_run.score(case, "I will do it myself, then verify.")
    assert not ok
    assert any("delegate|subagent" in line for line in failures)


def test_forbidden_accepts_alternates():
    case = _case()
    case["expect"]["must_not_mention"] = ["AskQuestion|AskUserQuestion"]
    ok, failures = eval_run.score(case, "Loading poteto-mode, will verify after. Then AskUserQuestion.")
    assert not ok
    assert any("forbidden present" in line for line in failures)
