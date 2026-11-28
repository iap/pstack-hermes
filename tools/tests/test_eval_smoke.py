"""Tests for the deterministic-first smoke entry point (#260)."""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "eval_smoke", ROOT / "tools" / "evals" / "smoke.py"
)
assert SPEC and SPEC.loader
smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke)


def test_default_checks_are_deterministic_only():
    checks = smoke.select_checks(live=False, model=None)

    names = [name for name, _tier in checks]
    assert "validate" in names
    assert "check_docs" in names
    assert "scanner_vocab" in names
    assert "dual_lock" in names
    assert "plugin_doctor" in names
    assert "seed_home_baseline" in names
    assert "trajectory_negative" in names
    assert all(tier == "deterministic" for _name, tier in checks)
    assert "activation" not in names
    assert "delegate" not in names


def test_live_checks_require_an_explicit_model():
    with pytest.raises(ValueError, match="model"):
        smoke.select_checks(live=True, model=None)

    checks = smoke.select_checks(live=True, model="tencent/hy4-flash:free")
    assert any(name == "activation" and tier == "live" for name, tier in checks)
    assert any(name == "delegate" and tier == "live" for name, tier in checks)


def test_record_carries_tiers_host_and_model():
    record = smoke.make_record(
        [{"name": "validate", "tier": "deterministic", "status": "pass", "detail": "ok"}],
        host={"platform": "test"},
        model="tencent/hy4-flash:free",
    )

    assert record["schema_version"] == "1"
    assert record["checks"][0]["tier"] == "deterministic"
    assert record["model"] == "tencent/hy4-flash:free"
    assert record["summary"] == {"pass": 1, "fail": 0, "error": 0}


def test_seed_home_check_detects_baseline_contamination(tmp_path):
    active = tmp_path / "active"
    active.mkdir()
    (active / "config.yaml").write_text("plugins:\n  enabled: []\n", encoding="utf-8")

    result = smoke.check_seed_home(ROOT, active)

    assert result["status"] == "pass", result["detail"]


def test_seed_home_prunes_alternate_checkout_skills(tmp_path):
    import tempfile

    alt = tmp_path / "other-checkout"
    (alt / "skills").mkdir(parents=True)
    active = tmp_path / "active"
    active.mkdir()
    (active / "config.yaml").write_text(
        f"skills:\n  external_dirs:\n    - {alt / 'skills'}\n", encoding="utf-8"
    )

    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp)
        smoke.run.seed_home(home, active, register_checkout_skills=False, skills_root=alt)
        data = smoke.yaml.safe_load((home / "config.yaml").read_text(encoding="utf-8"))
        dirs = (data.get("skills") or {}).get("external_dirs") or []

    assert str(alt / "skills") not in dirs


def test_write_record_creates_parent_directory(tmp_path):
    target = tmp_path / "new" / "dir" / "record.json"

    smoke.write_record({"schema_version": "1", "checks": []}, target)

    assert target.is_file()


def test_resolve_root_makes_relative_path_absolute(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    assert smoke.resolve_root(Path("some-checkout")) == (tmp_path / "some-checkout").resolve()


def test_runner_errors_are_detected_from_provider_diagnostics():
    assert smoke.is_runner_error("provider 429 rate_limit_exceeded")
    assert not smoke.is_runner_error("OK")


def test_summary_counts_runner_errors():
    record = smoke.make_record(
        [{"name": "delegate", "tier": "live", "status": "error", "detail": "timeout"}],
        host={"platform": "test"},
    )

    assert record["summary"] == {"pass": 0, "fail": 0, "error": 1}


def test_first_line_handles_empty_output():
    assert smoke.first_line("") == "unknown"
    assert smoke.first_line("v1\nnext") == "v1"


def test_trajectory_negative_check_is_default_deny():
    result = smoke.check_trajectory_negative()

    assert result["status"] == "pass", result["detail"]


def test_runner_error_line_returns_first_matching_line():
    assert smoke.runner_error_line("all good\nprovider 429 limit\nother") == "provider 429 limit"
    assert smoke.runner_error_line("all good") == "no output"


def test_live_delegate_prunes_the_selected_root(tmp_path, monkeypatch):
    captured = {}

    def fake_seed(home, active, register_checkout_skills=True, skills_root=None):
        captured["skills_root"] = skills_root

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        raise OSError("stop")

    monkeypatch.setattr(smoke.run, "seed_home", fake_seed)
    monkeypatch.setattr(smoke.subprocess, "run", fake_run)
    root = tmp_path / "other-checkout"
    entry = smoke.live_delegate(root, tmp_path / "home", "hermes", "model")

    assert captured["skills_root"] == root
    assert entry["status"] == "error"


def test_live_activation_selects_the_seeded_skill(tmp_path, monkeypatch):
    quote = "The Principles section below grounds every trigger."
    root = tmp_path / "checkout"
    (root / "skills" / "poteto-mode").mkdir(parents=True)
    (root / "skills" / "poteto-mode" / "SKILL.md").write_text(quote, encoding="utf-8")

    def fake_seed(home, active, register_checkout_skills=True, skills_root=None):
        snapshot = home / smoke.run.SKILL_SNAPSHOT / "poteto-mode"
        snapshot.mkdir(parents=True)
        (snapshot / "SKILL.md").write_text(quote, encoding="utf-8")
        (home / "config.yaml").write_text(
            f"skills:\n  external_dirs:\n  - '{home / smoke.run.SKILL_SNAPSHOT}'\n",
            encoding="utf-8",
        )

    captured = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        return subprocess.CompletedProcess(argv, 0, quote, "")

    monkeypatch.setattr(smoke.run, "seed_home", fake_seed)
    monkeypatch.setattr(smoke.subprocess, "run", fake_run)
    entry = smoke.live_activation(root, tmp_path / "home", "hermes", "model")

    assert captured["argv"][captured["argv"].index("-s") + 1] == "poteto-mode"
    assert entry["status"] == "pass"


def test_seed_home_prunes_equivalent_checkout_path(tmp_path):
    checkout = tmp_path / "checkout"
    active = tmp_path / "active"
    active.mkdir()
    (active / "config.yaml").write_text(
        smoke.yaml.safe_dump(
            {"skills": {"external_dirs": [str(checkout / "skills") + "/"]}}
        ),
        encoding="utf-8",
    )
    home = tmp_path / "home"

    smoke.run.seed_home(home, active, register_checkout_skills=False, skills_root=checkout)

    data = smoke.yaml.safe_load((home / "config.yaml").read_text(encoding="utf-8"))
    assert data["skills"]["external_dirs"] == []
