"""Regression tests for the PR checklist validator (standalone refactor, #156).

The provenance-block pin comparison died with the upstream converter; only
the checked-box evidence gate remains. These cover the evidence rules the
first live CI run exposed: a bare checked box is flagged, a fenced code
block counts as evidence, and boxes outside the Verification section are
scope declarations, not claims.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "pr_checklist", Path(__file__).resolve().parents[1] / "pr_checklist.py"
)
assert _SPEC and _SPEC.loader
pr_checklist = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(pr_checklist)


def _write(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "body.md"
    p.write_text(body, encoding="utf-8")
    return p


def test_checked_box_without_evidence_is_flagged(tmp_path: Path) -> None:
    body = _write(tmp_path, "## Verification\n- [x] `pytest -q`\n")
    assert pr_checklist.main([str(body)]) == 1


def test_fenced_block_counts_as_evidence(tmp_path: Path) -> None:
    body = _write(
        tmp_path,
        "## Verification\n- [x] `pytest -q`\n```\n40 passed\n```\n",
    )
    assert pr_checklist.main([str(body)]) == 0


def test_boxes_outside_verification_need_no_evidence(tmp_path: Path) -> None:
    """Scope declarations are not verification claims."""
    body = _write(
        tmp_path,
        "## Affected surface\n- [x] tooling\n- [x] docs\n"
        "## Verification\n"
        "- [x] `pytest -q`\n      ```\n      40 passed\n      ```\n",
    )
    assert pr_checklist.main([str(body)]) == 0


def test_html_comment_placeholders_are_ignored(tmp_path: Path) -> None:
    body = _write(
        tmp_path,
        "<!--\n- [ ] `pytest -q`\n      ```\n      <output>\n      ```\n-->\n"
        "## Verification\n"
        "- [x] `pytest -q`\n      ```\n      40 passed\n      ```\n",
    )
    assert pr_checklist.main([str(body)]) == 0


def test_docs_only_pr_is_not_a_failure(tmp_path: Path) -> None:
    body = _write(tmp_path, "## What changed\njust prose\n")
    assert pr_checklist.main([str(body)]) == 0


def test_shipped_template_passes_its_own_validator() -> None:
    """The repo's own PR template must not fail the check it defines."""
    repo = Path(__file__).resolve().parents[2]
    template = repo / ".github" / "PULL_REQUEST_TEMPLATE.md"
    if not template.is_file():  # pragma: no cover - template always ships
        pytest.skip("template not present")
    assert pr_checklist.main([str(template)]) == 0
