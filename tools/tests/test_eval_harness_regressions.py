"""Regressions for eval-harness false positives/negatives found in audit.

Each test calls the shipped code the way its callers do and asserts the
outcome a correct harness must produce. Run before the fixes to prove binding.
"""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "evals"))


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


install_smoke = _load("install_smoke", "tools/evals/install_smoke.py")
trajectory = _load("trajectory", "tools/evals/trajectory.py")
run = _load("eval_run", "tools/evals/run.py")


def test_pin_refusal_does_not_match_unrelated_pin_words():
    assert not install_smoke.is_pinned_install_refusal("The pin was removed")
    assert not install_smoke.is_pinned_install_refusal("pinned dependency")
    assert install_smoke.is_pinned_install_refusal(
        "Plugin 'pstack' is pinned; reinstall with an explicit --ref to change it."
    )


def test_listing_contains_handles_nested_json():
    assert install_smoke.listing_contains({"plugins": {"pstack": {}}}, "pstack")
    assert install_smoke.listing_contains([{"plugin": {"name": "pstack"}}], "pstack")
    assert not install_smoke.listing_contains({"plugins": {"other": {}}}, "pstack")


def test_wrapped_or_compound_commands_never_verify_a_claim():
    """Default-deny: parsing shell wrappers reliably is not possible here.

    A wrapped, quoted or compound command may have masked the test's exit
    status, so none of these may be treated as verification evidence. Missing
    evidence must not become a pass.
    """
    for command in (
        "bash -c 'pytest -q'",
        'sh -c "pytest -q"',
        "timeout 60 pytest -q",
        "env FOO=bar timeout 60 pytest -q",
        "cd repo && timeout 60 pytest -q",
        "pytest -q || true",
        "pytest -q | tee out",
        "bash -c 'pytest -q || true' | tee out",
        "echo 'x; pytest -q'",
        "pytest -q --rootdir='C:\\' || true",
    ):
        assert trajectory._verification_segment(command) is None, command
        assert not trajectory._is_test_command(command), command


def test_bare_test_commands_still_verify():
    assert trajectory._is_test_command("pytest -q")
    assert trajectory._is_test_command("uv run --frozen pytest -q")
    assert trajectory._is_test_command("python -m pytest tools/tests")
    assert trajectory._is_test_command("npm test")


def test_baseline_runner_error_is_data_not_a_gate_failure(monkeypatch):
    monkeypatch.setattr(run, "preflight", lambda *a, **k: (True, "hermes ok"))
    monkeypatch.setattr(
        run,
        "load_golden",
        lambda *a, **k: [{"id": "demo", "prompt": "do it", "expect": {}}],
    )
    monkeypatch.setattr(
        run,
        "run_case",
        lambda case, hermes, arm, model, timeout: (
            ("error", ["runner error"], []) if arm == "baseline" else ("pass", [], [])
        ),
    )
    assert run.main(["--arm", "both", "--hermes", "hermes"]) == 0


def test_skill_arm_runner_error_still_fails_the_sweep(monkeypatch):
    monkeypatch.setattr(run, "preflight", lambda *a, **k: (True, "hermes ok"))
    monkeypatch.setattr(
        run,
        "load_golden",
        lambda *a, **k: [{"id": "demo", "prompt": "do it", "expect": {}}],
    )
    monkeypatch.setattr(
        run,
        "run_case",
        lambda case, hermes, arm, model, timeout: (
            ("error", ["runner error"], []) if arm == "skill" else ("pass", [], [])
        ),
    )
    assert run.main(["--arm", "both", "--hermes", "hermes"]) == 2


def test_later_rejected_test_call_does_not_fall_back_to_an_earlier_one():
    """A rejected later test attempt makes the gate unavailable.

    Otherwise a passing `pytest -q`, followed by a rejected quoted or
    redirected test run, would cite the earlier result and report a false
    pass for a claim the later run may have disproved.
    """
    for later in ("pytest -q -k 'broken'", "pytest -q 2>&1", "pytest -q > out.txt"):
        calls = [
            {"name": "terminal", "args": {"command": "pytest -q"}, "exit_code": 0},
            {"name": "terminal", "args": {"command": later}, "exit_code": 0},
        ]
        result = trajectory.grade(
            {"gates": ["verify_before_claim"]}, calls, "All tests pass - 10 passed.", Path(".")
        )[0]
        assert result["status"] == "unavailable", (later, result)


def _grade_test_claim(calls):
    return trajectory.grade(
        {"gates": ["verify_before_claim"]}, calls, "All tests pass - 10 passed.", Path(".")
    )[0]


def test_unrelated_version_flag_cannot_hide_a_rejected_test():
    """A --version on another command must not reuse an earlier passing run.

    `pytest -q > out.txt` is rejected by the strict check; the trailing
    `python --version` must not suppress that rejection.
    """
    calls = [
        {"name": "terminal", "args": {"command": "pytest -q"}, "exit_code": 0},
        {
            "name": "terminal",
            "args": {"command": "pytest -q > out.txt; python --version"},
            "exit_code": 0,
        },
    ]
    assert _grade_test_claim(calls)["status"] == "unavailable"


def test_accepted_retry_after_rejection_is_graded():
    """A final bare pytest -q must be graded, not shadowed by an earlier rejected attempt."""
    calls = [
        {"name": "terminal", "args": {"command": "pytest -q"}, "exit_code": 0},
        {"name": "terminal", "args": {"command": "pytest -q -k 'broken'"}, "exit_code": 0},
        {"name": "terminal", "args": {"command": "pytest -q"}, "exit_code": 0},
    ]
    assert _grade_test_claim(calls)["status"] == "pass"


def test_baseline_only_sweep_with_errors_exits_nonzero(monkeypatch):
    """A baseline-only sweep with runner errors has no measurement at all."""
    monkeypatch.setattr(run, "preflight", lambda *a, **k: (True, "hermes ok"))
    monkeypatch.setattr(
        run,
        "load_golden",
        lambda *a, **k: [{"id": "demo", "prompt": "do it", "expect": {}}],
    )
    monkeypatch.setattr(
        run,
        "run_case",
        lambda *a, **k: ("error", ["runner error"], []),
    )
    assert run.main(["--arm", "baseline", "--hermes", "hermes"]) == 2


def test_later_wrapped_test_attempt_is_unavailable():
    """A wrapped test run after an accepted one must not be ignored."""
    for later in ("bash -c 'pytest -q'", "timeout 60 pytest -q"):
        calls = [
            {"name": "terminal", "args": {"command": "pytest -q"}, "exit_code": 0},
            {"name": "terminal", "args": {"command": later}, "exit_code": 0},
        ]
        result = _grade_test_claim(calls)
        assert result["status"] == "unavailable", (later, result)


def test_or_chain_skipping_test_cannot_verify():
    """`true || pytest -q` exits 0 without running the test."""
    assert trajectory._verification_segment("true || pytest -q") is None
    calls = [{"name": "terminal", "args": {"command": "true || pytest -q"}, "exit_code": 0}]
    assert trajectory.grade(
        {"gates": ["verify_before_claim"]}, calls, "All tests pass - 10 passed.", Path(".")
    )[0]["status"] != "pass"


def test_quoted_non_running_value_still_flags_a_later_rejection():
    """--help inside a quoted option value is not a bare non-running call."""
    calls = [
        {"name": "terminal", "args": {"command": "pytest -q"}, "exit_code": 0},
        {
            "name": "terminal",
            "args": {"command": "pytest -q --junit-prefix=' --help '"},
            "exit_code": 0,
        },
    ]
    assert _grade_test_claim(calls)["status"] == "unavailable"


def test_bare_non_running_flag_is_still_excluded():
    assert not trajectory._looks_like_test_command("pytest --help")


def test_non_test_or_chain_is_not_masked_evidence():
    """An OR chain with no test attempt must not hide a missing test run."""
    assert not trajectory._masked_test("true || false")
    calls = [{"name": "terminal", "args": {"command": "true || false"}, "exit_code": 0}]
    result = trajectory.grade(
        {"gates": ["verify_before_claim"]}, calls, "All tests pass - 10 passed.", Path(".")
    )[0]
    assert result["status"] == "fail"


def test_filename_argument_is_not_a_later_test_attempt():
    """A non-test command naming pytest.ini must not invalidate evidence."""
    assert not trajectory._looks_like_test_command("git diff -- pytest.ini")
    calls = [
        {"name": "terminal", "args": {"command": "pytest -q"}, "exit_code": 0},
        {"name": "terminal", "args": {"command": "git diff -- pytest.ini"}, "exit_code": 0},
    ]
    result = trajectory.grade(
        {"gates": ["verify_before_claim"]}, calls, "All tests pass - 10 passed.", Path(".")
    )[0]
    assert result["status"] == "pass"

