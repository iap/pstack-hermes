"""check_action_shell must actually fail on a broken composite step.

actionlint does not lint .github/actions steps (verified against 1.7.12: an
injected shell error in a referenced composite action goes unreported), which is
why this gate exists. A gate that cannot fail is not a gate, so these tests pin
the failing path and not just the happy one.
"""

import shutil
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_action_shell  # noqa: E402

needs_shellcheck = pytest.mark.skipif(
    shutil.which("shellcheck") is None,
    reason="shellcheck not on PATH; run under `uv run --frozen pytest`",
)


def _action_tree(tmp_path: Path, doc: dict) -> Path:
    act = tmp_path / ".github" / "actions" / "demo"
    act.mkdir(parents=True)
    (act / "action.yml").write_text(yaml.safe_dump(doc), encoding="utf-8")
    return tmp_path


def _composite(script: str) -> dict:
    return {
        "name": "demo",
        "description": "demo",
        "runs": {
            "using": "composite",
            "steps": [{"shell": "bash", "run": script}],
        },
    }


@needs_shellcheck
def test_clean_script_passes(tmp_path):
    root = _action_tree(tmp_path, _composite("set -euo pipefail\necho ok\n"))
    code, _ = check_action_shell.check(root)
    assert code == 0


@needs_shellcheck
def test_broken_shell_is_caught(tmp_path):
    # An unparseable test expression: shellcheck reports a parse error, which is
    # exactly the class of defect that slipped through with no gate.
    root = _action_tree(tmp_path, _composite("set -euo pipefail\nif [ ; then echo x; fi\n"))
    code, report = check_action_shell.check(root)
    assert code == 1
    assert any("FAIL" in line for line in report)


def test_missing_actions_dir_is_a_tool_error(tmp_path):
    code, report = check_action_shell.check(tmp_path)
    assert code == 2
    assert any("no actions directory" in line for line in report)


def test_non_composite_action_is_skipped(tmp_path):
    doc = {"name": "d", "description": "d", "runs": {"using": "node20", "main": "index.js"}}
    root = _action_tree(tmp_path, doc)
    code, report = check_action_shell.check(root)
    assert code == 0
    assert any("skip" in line for line in report)
