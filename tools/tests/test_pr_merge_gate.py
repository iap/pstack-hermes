"""Tests for the pre-merge bot-review gate (tools/pr_merge_gate.py).

Pure-function tests: no `gh`, no network. The CLI half is exercised by hand
before a merge; these tests pin the verdict logic the gate depends on, including
the four ways a naive name-only check could be fooled.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("pr_merge_gate", ROOT / "tools" / "pr_merge_gate.py")
assert SPEC and SPEC.loader
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


def run(name, conclusion, *, status="completed", app="coderabbitai"):
    return {
        "name": name,
        "status": status,
        "conclusion": conclusion,
        "app": {"slug": app} if app else None,
    }


BODY_CLEAN = """# Pull request

## Verification
- [x] things

## Bot review (gate)
- [x] Qodo findings triaged
- [x] CodeRabbit clean on this head
"""

CR_CLEAN = run("CodeRabbit", "success")
BUILD_OK = run("build (ubuntu-latest)", "success", app="github-actions")
QODO_OK = run("Qodo Merge", "success", app="qodo-ai")


def test_clean_rollup_and_body_pass():
    assert gate.evaluate([BUILD_OK, QODO_OK, CR_CLEAN], BODY_CLEAN) == []


def test_coderabbit_skipping_blocks():
    problems = gate.evaluate([CR_CLEAN | {"conclusion": "skipped"}], BODY_CLEAN)
    assert any("not clean" in p for p in problems)


def test_failed_coderabbit_blocks():
    problems = gate.evaluate([CR_CLEAN | {"conclusion": "failure"}], BODY_CLEAN)
    assert any("check failed: CodeRabbit" in p for p in problems)


def test_missing_coderabbit_check_blocks():
    problems = gate.evaluate([BUILD_OK], BODY_CLEAN)
    assert any("no CodeRabbit check" in p for p in problems)


def test_forged_coderabbit_name_blocks():
    forged = run("CodeRabbit", "success", app="evil-workflow")
    problems = gate.evaluate([forged], BODY_CLEAN)
    assert any("not 'coderabbitai'" in p for p in problems)


def test_unfinished_check_blocks():
    problems = gate.evaluate([CR_CLEAN, run("ci", "", status="in_progress", app="github-actions")], BODY_CLEAN)
    assert any("not finished: ci" in p for p in problems)


def test_failed_check_blocks():
    problems = gate.evaluate([CR_CLEAN, run("ci", "failure", app="github-actions")], BODY_CLEAN)
    assert any("check failed: ci" in p for p in problems)


def test_unchecked_bot_box_blocks():
    body = BODY_CLEAN.replace("- [x] CodeRabbit clean", "- [ ] CodeRabbit clean")
    problems = gate.evaluate([CR_CLEAN], body)
    assert any("bot-review box unchecked" in p for p in problems)


def test_missing_bot_section_blocks():
    body = "# Pull request\n\n## Verification\n- [x] things\n"
    problems = gate.evaluate([CR_CLEAN], body)
    assert any("no '## Bot review (gate)' section" in p for p in problems)


def test_boxes_outside_the_bot_section_are_ignored():
    body = BODY_CLEAN.replace("## Verification\n- [x] things", "## Verification\n- [ ] unrelated")
    assert gate.evaluate([CR_CLEAN], body) == []


def test_legacy_status_context_shape_is_accepted():
    rollup = [{"context": "CodeRabbit", "state": "success"}]
    problems = gate.evaluate(rollup, BODY_CLEAN)
    # No app provenance on a status context: treated as unverifiable, not clean.
    assert any("no app provenance" in p for p in problems)
