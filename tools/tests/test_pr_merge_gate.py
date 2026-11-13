"""Tests for the pre-merge bot-review gate (tools/pr_merge_gate.py).

Pure-function tests: no `gh`, no network. The CLI half is exercised by hand
before a merge; these tests pin the verdict logic the gate depends on.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "pr_merge_gate", ROOT / "tools" / "pr_merge_gate.py"
)
assert SPEC and SPEC.loader
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


def run(name, conclusion, status="COMPLETED"):
    return {"name": name, "status": status, "conclusion": conclusion}


BODY_CLEAN = """# Pull request

## Verification
- [x] things

## Bot review (gate)
- [x] Qodo findings triaged
- [x] CodeRabbit clean on this head
"""


def test_clean_rollup_and_body_pass():
    rollup = [run("ci", "SUCCESS"), run("CodeRabbit", "SUCCESS")]
    assert gate.evaluate(rollup, BODY_CLEAN) == []


def test_coderabbit_skipping_blocks():
    rollup = [run("ci", "SUCCESS"), run("CodeRabbit", "SKIPPED")]
    problems = gate.evaluate(rollup, BODY_CLEAN)
    assert any("CodeRabbit is not clean" in p for p in problems)


def test_coderabbit_pending_blocks():
    rollup = [run("CodeRabbit", "SUCCESS", status="IN_PROGRESS")]
    problems = gate.evaluate(rollup, BODY_CLEAN)
    assert any("CodeRabbit is not clean" in p for p in problems)


def test_missing_coderabbit_check_blocks():
    problems = gate.evaluate([run("ci", "SUCCESS")], BODY_CLEAN)
    assert any("no CodeRabbit check" in p for p in problems)


def test_failed_check_blocks():
    rollup = [run("ci", "FAILURE"), run("CodeRabbit", "SUCCESS")]
    problems = gate.evaluate(rollup, BODY_CLEAN)
    assert any("check failed: ci" in p for p in problems)


def test_unchecked_bot_box_blocks():
    body = BODY_CLEAN.replace("- [x] CodeRabbit clean on this head", "- [ ] CodeRabbit clean on this head")
    problems = gate.evaluate([run("CodeRabbit", "SUCCESS")], body)
    assert any("bot-review box unchecked" in p for p in problems)


def test_boxes_outside_the_bot_section_are_ignored():
    body = BODY_CLEAN.replace("## Verification\n- [x] things", "## Verification\n- [ ] an unrelated box")
    assert gate.evaluate([run("CodeRabbit", "SUCCESS")], body) == []


def test_status_context_shape_is_understood():
    rollup = [{"context": "CodeRabbit", "state": "SUCCESS"}]
    assert gate.evaluate(rollup, BODY_CLEAN) == []
