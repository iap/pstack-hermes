"""check_action_inputs must catch the exact defect that motivated it.

`.github/workflows/labeler.yml` passed `syncLabels` where the action declares
`sync-labels`. The runner logs "Unexpected input(s)" and silently ignores the
value - label sync stayed off while the step comment promised it. The defect
passed actionlint and the entire test suite (both re-verified by reintroducing
it), so these tests pin the counterfactual: the check fails on the undeclared
key, and passes once the key is corrected.
"""

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_action_inputs  # noqa: E402


def _workflow(tmp_path: Path, uses: str, with_: dict | None = None) -> Path:
    step: dict = {"uses": uses}
    if with_ is not None:
        step["with"] = with_
    doc = {
        "name": "t",
        "on": ["push"],
        "jobs": {"j": {"runs-on": "ubuntu-latest", "steps": [step]}},
    }
    d = tmp_path / ".github" / "workflows"
    d.mkdir(parents=True, exist_ok=True)
    (d / "t.yml").write_text(yaml.safe_dump(doc), encoding="utf-8")
    return tmp_path


def _local_action_with_inputs(tmp_path: Path, inputs: list[str]) -> Path:
    return _write_action(
        tmp_path,
        "demo",
        {k: {"description": k, "required": False} for k in inputs},
        [{"shell": "bash", "run": "true"}],
    )


def _write_action(tmp_path: Path, name: str, inputs: dict, steps: list[dict]) -> Path:
    d = tmp_path / ".github" / "actions" / name
    d.mkdir(parents=True, exist_ok=True)
    doc = {
        "name": name,
        "description": name,
        "inputs": inputs,
        "runs": {"using": "composite", "steps": steps},
    }
    (d / "action.yml").write_text(yaml.safe_dump(doc), encoding="utf-8")
    return tmp_path


def test_declared_input_passes(tmp_path):
    _local_action_with_inputs(tmp_path, ["sync-labels", "configuration-path"])
    _workflow(tmp_path, "./.github/actions/demo", {"sync-labels": True})
    code, _ = check_action_inputs.check(tmp_path, fetch=lambda url: None)
    assert code == 0


def test_undeclared_input_is_caught_the_labeler_case(tmp_path):
    """The counterfactual: `syncLabels` is not `sync-labels`."""
    _local_action_with_inputs(tmp_path, ["sync-labels"])
    _workflow(tmp_path, "./.github/actions/demo", {"syncLabels": True})
    code, report = check_action_inputs.check(tmp_path, fetch=lambda url: None)
    assert code == 1
    assert any("FAIL" in line and "syncLabels" in line for line in report)


def test_remote_action_unknown_input_is_caught(tmp_path):
    _workflow(tmp_path, "actions/labeler@" + "a" * 40, {"syncLabels": True})
    body = yaml.safe_dump({"inputs": {"sync-labels": {"description": "x"}}})
    url = check_action_inputs.RAW_URL.format(repo="actions/labeler", ref="a" * 40,
                                             name="action.yml")
    code, report = check_action_inputs.check(
        tmp_path, fetch=lambda u: body if u == url else None
    )
    assert code == 1
    assert any("syncLabels" in line for line in report)


def test_action_yaml_fallback(tmp_path):
    _workflow(tmp_path, "actions/labeler@" + "b" * 40, {"repo-token": "x"})
    body = yaml.safe_dump({"inputs": {"repo-token": {"description": "x"}}})
    yml = check_action_inputs.RAW_URL.format(repo="actions/labeler", ref="b" * 40,
                                             name="action.yml")
    yaml_ = check_action_inputs.RAW_URL.format(repo="actions/labeler", ref="b" * 40,
                                               name="action.yaml")
    code, _ = check_action_inputs.check(
        tmp_path, fetch=lambda u: None if u == yml else (body if u == yaml_ else None)
    )
    assert code == 0


def test_unresolvable_action_is_a_tool_error_not_a_pass(tmp_path):
    _workflow(tmp_path, "actions/labeler@" + "c" * 40, {"x": "1"})
    code, report = check_action_inputs.check(tmp_path, fetch=lambda url: None)
    assert code == 2  # cannot certify inputs it could not read
    assert any("cannot resolve" in line for line in report)


def test_docker_reference_is_skipped(tmp_path):
    _workflow(tmp_path, "docker://alpine:3.20", {"entrypoint": "/bin/sh"})
    code, report = check_action_inputs.check(tmp_path, fetch=lambda url: None)
    assert code == 0
    assert any("skip" in line for line in report)


def test_step_without_with_is_fine(tmp_path):
    _write_action(tmp_path, "demo", {}, [{"shell": "bash", "run": "true"}])
    _workflow(tmp_path, "./.github/actions/demo")
    code, _ = check_action_inputs.check(tmp_path, fetch=lambda url: None)
    assert code == 0


def test_composite_action_steps_are_scanned_too(tmp_path):
    """The check covers .github/actions/*/action.yml, not only workflows."""
    _local_action_with_inputs(tmp_path, ["good-input"])
    _write_action(
        tmp_path,
        "caller",
        {},
        [{"uses": "./.github/actions/demo", "with": {"badInput": "1"}}],
    )
    code, report = check_action_inputs.check(tmp_path, fetch=lambda url: None)
    assert code == 1
    assert any("badInput" in line for line in report)


def test_broken_yaml_is_a_tool_error(tmp_path):
    d = tmp_path / ".github" / "workflows"
    d.mkdir(parents=True)
    (d / "broken.yml").write_text("jobs: [unclosed\n", encoding="utf-8")
    code, report = check_action_inputs.check(tmp_path, fetch=lambda url: None)
    assert code == 2
    assert any("unparseable" in line or "cannot resolve" in line for line in report)
