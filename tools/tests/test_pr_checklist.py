"""Regression tests for the PR checklist validator.

These cover the two bugs the first live CI run exposed: the advisory job
leaking the validator's exit code, and the evidence rule demanding an
"Evidence:" label when the template actually asks for a fenced code block.
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


PROVENANCE = "93b00b89ef425a9c1bac0d0b317dfc49c930ac99"


@pytest.fixture
def provenance_file(tmp_path: Path) -> Path:
    p = tmp_path / ".build-provenance.txt"
    p.write_text(
        f"package: pstack\nsource_commit: {PROVENANCE}\n"
        "converter: convert.py (sha256[:16]=ab4202be88f26e40)\n",
        encoding="utf-8",
    )
    return p


def _write(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "body.md"
    p.write_text(body, encoding="utf-8")
    return p


def test_matching_pin_passes(tmp_path: Path, provenance_file: Path) -> None:
    body = _write(
        tmp_path,
        "## Verification\n"
        f"```yaml\nsource_commit: {PROVENANCE}\n```\n"
        "- [x] `pytest -q`\n      ```\n      40 passed\n      ```\n",
    )
    assert pr_checklist.main([str(body), "--provenance", str(provenance_file)]) == 0


def test_wrong_pin_is_rejected(tmp_path: Path, provenance_file: Path) -> None:
    body = _write(
        tmp_path,
        "## Verification\n"
        "```yaml\nsource_commit: deadbeefdeadbeefdeadbeefdeadbeefdeadbeef\n```\n"
        "- [x] `pytest -q`\n      ```\n      40 passed\n      ```\n",
    )
    assert pr_checklist.main([str(body), "--provenance", str(provenance_file)]) == 1


def test_checked_box_without_evidence_is_flagged(tmp_path: Path, provenance_file: Path) -> None:
    body = _write(
        tmp_path,
        f"## Verification\n```yaml\nsource_commit: {PROVENANCE}\n```\n- [x] `pytest -q`\n",
    )
    assert pr_checklist.main([str(body), "--provenance", str(provenance_file)]) == 1


def test_fenced_block_counts_as_evidence(tmp_path: Path, provenance_file: Path) -> None:
    """The template asks for a fenced block, not an 'Evidence:' label."""
    body = _write(
        tmp_path,
        f"## Verification\n```yaml\nsource_commit: {PROVENANCE}\n```\n"
        "- [x] `pytest -q`\n      ```\n      40 passed\n      ```\n",
    )
    assert pr_checklist.main([str(body), "--provenance", str(provenance_file)]) == 0


def test_boxes_outside_verification_need_no_evidence(
    tmp_path: Path, provenance_file: Path
) -> None:
    """Scope declarations are not verification claims."""
    body = _write(
        tmp_path,
        "## Affected surface\n- [x] tooling\n- [x] docs\n"
        f"## Verification\n```yaml\nsource_commit: {PROVENANCE}\n```\n"
        "- [x] `pytest -q`\n      ```\n      40 passed\n      ```\n",
    )
    assert pr_checklist.main([str(body), "--provenance", str(provenance_file)]) == 0


def test_html_comment_placeholders_are_ignored(
    tmp_path: Path, provenance_file: Path
) -> None:
    body = _write(
        tmp_path,
        "<!--\n- [ ] `pytest -q`\n      ```\n      <output>\n      ```\n-->\n"
        f"## Verification\n```yaml\nsource_commit: {PROVENANCE}\n```\n"
        "- [x] `pytest -q`\n      ```\n      40 passed\n      ```\n",
    )
    assert pr_checklist.main([str(body), "--provenance", str(provenance_file)]) == 0


def test_unfilled_placeholder_is_not_a_mismatch(
    tmp_path: Path, provenance_file: Path
) -> None:
    body = _write(
        tmp_path,
        "## Verification\n```yaml\nsource_commit: <40-char SHA>\n```\n"
        "- [x] `pytest -q`\n      ```\n      40 passed\n      ```\n",
    )
    assert pr_checklist.main([str(body), "--provenance", str(provenance_file)]) == 0


def test_docs_only_pr_is_not_a_failure(tmp_path: Path, provenance_file: Path) -> None:
    body = _write(tmp_path, "## What changed\njust prose\n")
    assert pr_checklist.main([str(body), "--provenance", str(provenance_file)]) == 0


def test_shipped_template_passes_its_own_validator(
    tmp_path: Path, provenance_file: Path
) -> None:
    """The repo's own PR template must not fail the check it defines."""
    repo = Path(__file__).resolve().parents[2]
    template = repo / ".github" / "PULL_REQUEST_TEMPLATE.md"
    if not template.is_file():  # pragma: no cover - template always ships
        pytest.skip("template not present")
    assert pr_checklist.main([str(template), "--provenance", str(provenance_file)]) == 0
