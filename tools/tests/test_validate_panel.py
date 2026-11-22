"""Stage-D consistency: the shipped panel must equal the repo-owned asset."""

import json
from pathlib import Path

import validate
from validate import MODEL_SLUG_RE


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


def test_duplicate_lanes_in_a_role_array_fail(tmp_path):
    payload = {"roles": {"arena runners": ["m/a", "m/b", "m/a"]}}
    asset = _write_asset(tmp_path, payload)
    pkg = tmp_path / "pkg"
    _write_config(pkg, payload)

    rep = validate.Report()
    validate.check_model_panel(pkg, rep, asset=asset)

    joined = "\n".join(rep.failed)
    assert "duplicate" in joined
    assert "arena runners" in joined


def test_repeated_inherit_parent_selectors_are_allowed(tmp_path):
    """N copies of the selector = N lanes on the parent model (supported
    fan-out shape); only duplicate PROVIDER slugs are accidental."""
    payload = {"roles": {"how critics": ["inherit-parent", "inherit-parent"]}}
    asset = _write_asset(tmp_path, payload)
    pkg = tmp_path / "pkg"
    _write_config(pkg, payload)

    rep = validate.Report()
    validate.check_model_panel(pkg, rep, asset=asset)

    assert not rep.failed


def test_shipped_panel_has_no_dead_slugs():
    """The shipped config/models.json and the repo-owned panel must not
    name a slug absent from the provider catalog (regression for the
    meituan/longcat-2.0 default that failed the weekly model-drift-watch).
    Every role value is either the inherit-parent selector or a
    provider-qualified slug; the two files stay byte-identical.
    """
    root = Path(__file__).resolve().parents[2]
    config = root / "config" / "models.json"
    panel = root / "tools" / "assets" / "model-panel.json"
    assert config.read_bytes() == panel.read_bytes()
    for path in (config, panel):
        roles = json.loads(path.read_text(encoding="utf-8")).get("roles", {})
        assert len(roles) == 18, path
        for role, value in roles.items():
            vals = value if isinstance(value, list) else [value]
            assert vals, (path, role)
            for slug in vals:
                assert slug == "inherit-parent" or MODEL_SLUG_RE.match(slug), (path, role, slug)
    assert "meituan/longcat-2.0" not in config.read_text(encoding="utf-8")
    assert "meituan/longcat-2.0" not in panel.read_text(encoding="utf-8")

