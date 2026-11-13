"""Tests for the installed-user lifecycle test (tools/evals/install_smoke.py).

The install itself needs a healthy ``hermes`` CLI, so these tests cover the
deterministic half: locating an installed tree, the structural assertions that
encode #168 (root scripts survive packaging) and #169 (dual lockfile), the
post-remove absence check, and tolerant parsing of `hermes plugins list --json`.
"""

from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "install_smoke", ROOT / "tools" / "evals" / "install_smoke.py"
)
assert SPEC and SPEC.loader
smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke)


def make_tree(base: Path, skills: int = 2) -> Path:
    """Minimal installed-tree fixture with every shipped component."""
    tree = base / "plugins" / "pstack"
    (tree / "skills").mkdir(parents=True)
    (tree / "scripts").mkdir()
    (tree / "config").mkdir()
    (tree / "plugin.json").write_text('{"name": "pstack", "version": "0.0.0"}', encoding="utf-8")
    for i in range(skills):
        d = tree / "skills" / f"skill-{i}"
        d.mkdir()
        (d / "SKILL.md").write_text("# skill\n", encoding="utf-8")
    (tree / "scripts" / "orch").write_text("#!/bin/sh\n", encoding="utf-8")
    (tree / "scripts" / "watch-pr").write_text("#!/bin/sh\n", encoding="utf-8")
    (tree / "package.json").write_text("{}", encoding="utf-8")
    (tree / "bun.lock").write_text("", encoding="utf-8")
    (tree / "package-lock.json").write_text("{}", encoding="utf-8")
    (tree / "config" / "models.json").write_text("{}", encoding="utf-8")
    return tree


def test_complete_tree_passes(tmp_path):
    tree = make_tree(tmp_path, skills=3)
    facts = smoke.assert_tree(tree, expected_skills=3)
    assert facts["skills"] == "3"
    assert "orch" in facts["scripts"]


def test_missing_root_script_fails_168(tmp_path):
    tree = make_tree(tmp_path)
    (tree / "scripts" / "orch").unlink()
    with pytest.raises(smoke.StepFailed, match="#168"):
        smoke.assert_tree(tree, expected_skills=2)


def test_missing_lockfile_fails_169(tmp_path):
    tree = make_tree(tmp_path)
    (tree / "package-lock.json").unlink()
    with pytest.raises(smoke.StepFailed, match="#169"):
        smoke.assert_tree(tree, expected_skills=2)


def test_skill_count_mismatch_fails(tmp_path):
    tree = make_tree(tmp_path, skills=2)
    with pytest.raises(smoke.StepFailed, match="installed 2 skills"):
        smoke.assert_tree(tree, expected_skills=3)


def test_no_skills_fails(tmp_path):
    tree = make_tree(tmp_path, skills=0)
    with pytest.raises(smoke.StepFailed, match="no skills"):
        smoke.assert_tree(tree, expected_skills=None)


def test_missing_config_panel_fails(tmp_path):
    tree = make_tree(tmp_path)
    (tree / "config" / "models.json").unlink()
    with pytest.raises(smoke.StepFailed, match="config/models.json"):
        smoke.assert_tree(tree, expected_skills=2)


def test_find_installed_locates_tree(tmp_path):
    tree = make_tree(tmp_path)
    assert smoke.find_installed(tmp_path) == tree


def test_find_installed_reports_when_absent(tmp_path):
    (tmp_path / "home").mkdir()
    with pytest.raises(smoke.StepFailed, match="no installed package"):
        smoke.find_installed(tmp_path / "home")


def test_count_skills_counts_only_skill_manifests(tmp_path):
    tree = make_tree(tmp_path, skills=4)
    (tree / "skills" / "stray.txt").write_text("x", encoding="utf-8")
    assert smoke.count_skills(tree) == 4


def test_assert_absent_passes_after_remove(tmp_path):
    tree = make_tree(tmp_path)
    shutil.rmtree(tree)
    smoke.assert_absent(tmp_path)  # must not raise


def test_assert_absent_fails_when_directory_remains(tmp_path):
    make_tree(tmp_path)
    with pytest.raises(smoke.StepFailed, match="remove left the install directory"):
        smoke.assert_absent(tmp_path)


def test_listing_contains_handles_list_of_objects():
    entries = [{"name": "other"}, {"name": "pstack"}]
    assert smoke.listing_contains(entries, "pstack")
    assert not smoke.listing_contains(entries, "pstack-hermes")


def test_listing_contains_handles_mapping_of_objects():
    entries = {"pstack": {"name": "pstack", "enabled": True}}
    assert smoke.listing_contains(entries, "pstack")


def test_listing_contains_ignores_unrelated_shapes():
    assert not smoke.listing_contains("not-a-listing", "pstack")
    assert not smoke.listing_contains([], "pstack")
