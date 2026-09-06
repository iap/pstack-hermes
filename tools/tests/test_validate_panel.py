"""Stage-D consistency: the shipped panel must equal the repo-owned asset."""

import json

import validate


def _panel(n=2):
    return {"roles": {f"role-{i}": "inherit-parent" for i in range(n)}}


def _write_config(pkg, payload):
    (pkg / "config").mkdir(parents=True, exist_ok=True)
    (pkg / "config" / "models.json").write_text(json.dumps(payload), encoding="utf-8")


def _write_asset(tmp_path, payload):
    asset = tmp_path / "panel.json"
    asset.write_text(json.dumps(payload), encoding="utf-8")
    return asset


def test_equal_panel_and_config_passes(tmp_path):
    asset = _write_asset(tmp_path, _panel(3))
    pkg = tmp_path / "pkg"
    _write_config(pkg, _panel(3))

    rep = validate.Report()
    validate.check_model_panel(pkg, rep, asset=asset)

    assert not rep.failed
    assert any("model panel" in p for p in rep.passed)


def test_drifted_config_fails(tmp_path):
    asset = _write_asset(tmp_path, _panel(2))
    pkg = tmp_path / "pkg"
    _write_config(pkg, _panel(3))

    rep = validate.Report()
    validate.check_model_panel(pkg, rep, asset=asset)

    assert rep.failed
    assert "model panel" in rep.failed[0]


def test_missing_config_with_asset_present_fails(tmp_path):
    asset = _write_asset(tmp_path, _panel())

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


def test_catalog_style_slugs_pass(tmp_path):
    payload = {"roles": {"r": ["z-ai/glm-5.2", "meituan/longcat-2.0:free"],
                         "s": "qwen/qwen-2.5-7b-instruct"}}
    asset = _write_asset(tmp_path, payload)
    pkg = tmp_path / "pkg"
    _write_config(pkg, payload)

    rep = validate.Report()
    validate.check_model_panel(pkg, rep, asset=asset)

    assert not rep.failed


def test_slug_check_catches_missing_vendor_prefix_and_case(tmp_path):
    payload = {"roles": {"r": "muse-spark-1.2-contributor-free",
                         "s": "Qwen/Qwen2.5-7B-Instruct"}}
    asset = _write_asset(tmp_path, payload)
    pkg = tmp_path / "pkg"
    _write_config(pkg, payload)

    rep = validate.Report()
    validate.check_model_panel(pkg, rep, asset=asset)

    joined = "\n".join(rep.failed)
    assert "muse-spark-1.2-contributor-free" in joined
    assert "Qwen/Qwen2.5-7B-Instruct" in joined


def test_non_string_slugs_reported_not_fatal(tmp_path):
    """Numeric/null role values must land in the report, not crash the
    validator with a TypeError inside the slug regex."""
    payload = {"roles": {"r": 42, "s": [7, "z-ai/glm-5.2"], "t": None}}
    asset = _write_asset(tmp_path, payload)
    pkg = tmp_path / "pkg"
    _write_config(pkg, payload)

    rep = validate.Report()
    validate.check_model_panel(pkg, rep, asset=asset)

    joined = "\n".join(rep.failed)
    assert "42" in joined
    assert "7" in joined
    assert "None" in joined
    # the one valid slug in the same payload is not reported
    assert "s: 'z-ai/glm-5.2'" not in joined
