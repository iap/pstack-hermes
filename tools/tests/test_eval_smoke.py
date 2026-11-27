"""Tests for the deterministic-first smoke entry point (#260)."""

from __future__ import annotations

import importlib.util
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
