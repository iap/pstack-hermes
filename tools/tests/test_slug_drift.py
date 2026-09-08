"""Slug drift: configured panel/config slugs vs the provider catalog ids."""

import json

import slug_drift


def _catalog(tmp_path, ids):
    p = tmp_path / "catalog.json"
    p.write_text(json.dumps({"data": [{"id": i} for i in ids]}), encoding="utf-8")
    return p


def _roles_file(tmp_path, name, roles):
    p = tmp_path / name
    p.write_text(json.dumps({"roles": roles}), encoding="utf-8")
    return p


def test_missing_slug_reported_with_role_and_slug(tmp_path):
    panel = _roles_file(tmp_path, "panel.json", {"why synthesizer": "z-ai/glm-5.2"})
    ids = slug_drift.load_catalog_file(_catalog(tmp_path, ["other/vendor-1"]))

    findings, checked = slug_drift.check([panel], ids)

    assert checked == 1
    assert len(findings) == 1
    assert "why synthesizer" in findings[0] and "z-ai/glm-5.2" in findings[0]


def test_selectors_and_non_strings_are_skipped(tmp_path):
    panel = _roles_file(tmp_path, "panel.json",
                        {"r": "inherit-parent", "s": [42, None, "meta/m-1"]})
    ids = slug_drift.load_catalog_file(_catalog(tmp_path, ["meta/m-1"]))

    findings, checked = slug_drift.check([panel], ids)

    assert findings == []
    assert checked == 1  # only the one real slug


def test_variant_suffix_matches_catalog_id_exactly(tmp_path):
    panel = _roles_file(tmp_path, "panel.json", {"r": ["vendor/m:free"]})
    ids = slug_drift.load_catalog_file(_catalog(tmp_path, ["vendor/m:free"]))

    findings, _ = slug_drift.check([panel], ids)

    assert findings == []


def test_every_path_is_checked_and_missing_files_are_findings(tmp_path):
    panel = _roles_file(tmp_path, "panel.json", {"r": "vendor/m"})
    absent = tmp_path / "config.json"
    ids = slug_drift.load_catalog_file(_catalog(tmp_path, ["vendor/m"]))

    findings, _ = slug_drift.check([panel, absent], ids)

    assert len(findings) == 1
    assert "config.json" in findings[0]


def test_clean_panel_and_config_pass(tmp_path):
    panel = _roles_file(tmp_path, "panel.json",
                        {"a": "vendor/m", "b": ["vendor/m", "other/x:free"]})
    cfg = _roles_file(tmp_path, "config.json", {"a": "vendor/m", "b": "inherit-parent"})
    ids = slug_drift.load_catalog_file(
        _catalog(tmp_path, ["vendor/m", "other/x:free"]))

    findings, checked = slug_drift.check([panel, cfg], ids)

    assert findings == []
    assert checked == 4  # panel 3 real slugs + config 1 (its selector is skipped)


def test_empty_catalog_is_an_error_not_a_clean_bill():
    import pytest

    with pytest.raises(ValueError):
        slug_drift.catalog_ids({"data": []})
