"""Stage-D consistency: the shipped panel must equal the repo-owned asset."""

import json

import validate


def _panel(n=2):
    return {"roles": {f"role-{i}": "inherit-parent" for i in range(n)}}


def _write_config(pkg, payload):
    (pkg / "config").mkdir(parents=True, exist_ok=True)
    (pkg / "config" / "models.json").write_text(json.dumps(payload), encoding="utf-8")


def test_equal_panel_and_config_passes(tmp_path):
    asset = tmp_path / "panel.json"
    asset.write_text(json.dumps(_panel(3)), encoding="utf-8")
    pkg = tmp_path / "pkg"
    _write_config(pkg, _panel(3))

    rep = validate.Report()
    validate.check_model_panel(pkg, rep, asset=asset)

    assert not rep.failed
    assert any("model panel" in p for p in rep.passed)


def test_drifted_config_fails(tmp_path):
    asset = tmp_path / "panel.json"
    asset.write_text(json.dumps(_panel(2)), encoding="utf-8")
    pkg = tmp_path / "pkg"
    _write_config(pkg, _panel(3))

    rep = validate.Report()
    validate.check_model_panel(pkg, rep, asset=asset)

    assert rep.failed
    assert "model panel" in rep.failed[0]


def test_missing_config_with_asset_present_fails(tmp_path):
    asset = tmp_path / "panel.json"
    asset.write_text(json.dumps(_panel()), encoding="utf-8")

    rep = validate.Report()
    validate.check_model_panel(tmp_path / "pkg", rep, asset=asset)

    assert rep.failed


def test_missing_asset_is_a_note_not_a_failure(tmp_path):
    pkg = tmp_path / "pkg"
    _write_config(pkg, _panel())

    rep = validate.Report()
    validate.check_model_panel(pkg, rep, asset=tmp_path / "absent-panel.json")

    assert not rep.failed
    assert rep.notes
