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


def test_prose_scan_finds_non_catalog_format_defaults(tmp_path):
    """Prose defaults that are not in OpenRouter vendor/model format are
    reported as informational findings; they do not fail the watch."""
    skills = tmp_path / "skills"
    (skills / "demo").mkdir(parents=True)
    (skills / "demo" / "SKILL.md").write_text(
        "Use `claude-fable-5-1-thinking-max` as the default.\n"
        "Also `claude-opus-5-thinking-xhigh` which is a prose-only default.\n",
        encoding="utf-8",
    )
    catalog = tmp_path / "catalog.json"
    catalog.write_text(json.dumps({"data": [{"id": "z-ai/glm-5.2"}]}), encoding="utf-8")
    ids = slug_drift.load_catalog_file(catalog)
    findings, checked = slug_drift.scan_prose(skills, ids)
    assert checked == 2
    assert len(findings) == 2
    assert all("not in OpenRouter vendor/model format" in f for f in findings)


def test_prose_scan_skips_tokens_without_a_version_component(tmp_path):
    """Tokens like `prompt` or `properties_json` are not model slugs and
    must not flood the drift alert."""
    skills = tmp_path / "skills"
    (skills / "demo").mkdir(parents=True)
    (skills / "demo" / "SKILL.md").write_text(
        "Use `prompt` and `properties_json` and `gpt-4`.\n",
        encoding="utf-8",
    )
    catalog = tmp_path / "catalog.json"
    catalog.write_text(json.dumps({"data": [{"id": "z-ai/glm-5.2"}]}), encoding="utf-8")
    ids = slug_drift.load_catalog_file(catalog)
    findings, checked = slug_drift.scan_prose(skills, ids)
    assert checked == 1  # only gpt-4 matches the slug regex
    assert len(findings) == 1
    assert "gpt-4" in findings[0]


def test_prose_scan_reports_vendor_model_slugs_missing_from_catalog(tmp_path):
    """A backtick-quoted vendor/model slug in prose that is not in the
    catalog is reported as a MISSING finding."""
    skills = tmp_path / "skills"
    (skills / "demo").mkdir(parents=True)
    (skills / "demo" / "SKILL.md").write_text(
        "Use `claude/missing-1.0` as the default.\n", encoding="utf-8")
    catalog = tmp_path / "catalog.json"
    catalog.write_text(json.dumps({"data": [{"id": "other/model"}]}), encoding="utf-8")
    ids = slug_drift.load_catalog_file(catalog)
    findings, checked = slug_drift.scan_prose(skills, ids)
    assert checked == 1
    assert len(findings) == 1
    assert "claude/missing-1.0" in findings[0]
    assert "not in the provider catalog" in findings[0]
