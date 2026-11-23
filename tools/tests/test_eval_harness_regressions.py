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


def test_test_command_detection_unwraps_shell_wrappers():
    assert trajectory._is_test_command("bash -c 'pytest -q'")
    assert trajectory._is_test_command('sh -c "pytest -q"')
    assert trajectory._is_test_command("timeout 60 pytest -q")
    assert trajectory._is_test_command("bash -c 'cd /proj && pytest -q'")


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


def test_masking_inside_and_after_shell_wrappers_is_detected():
    """A failed test hidden by a wrapper suffix must not verify a claim.

    The wrapper's exit status is the shell's, so an outer `|| true` or `| tee`
    records 0 even when pytest failed. Both segment grading and masking
    detection must see through the wrapper without dropping the suffix.
    """
    for command in (
        "bash -c 'pytest -q || true'",
        "bash -c 'pytest -q' || true",
        "bash -c 'pytest -q' | tee out",
        "timeout 60 pytest -q | tee out",
    ):
        assert trajectory._verification_segment(command) is None, command
        assert trajectory._masked_test(command), command

