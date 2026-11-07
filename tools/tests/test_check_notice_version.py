"""check_pins: NOTICE.md upstream version must match plugin.json.

NOTICE.md is hand-written, so a re-pin that bumps the upstream version
without editing NOTICE.md would ship a stale notice. The gate fails
closed when either file cannot be read.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_pins  # noqa: E402


def _tree(tmp_path, plugin_version="0.15.5", notice_version="0.15.5", notice=True, plugin=True):
    root = tmp_path
    if plugin:
        (root / "plugin.json").write_text(
            json.dumps({"name": "pstack", "version": plugin_version}),
            encoding="utf-8",
        )
    if notice:
        (root / "NOTICE.md").write_text(
            f"# NOTICE\n\n- Project: pstack v{notice_version}\n",
            encoding="utf-8",
        )
    return root


def test_matching_versions_pass(tmp_path):
    code, report = check_pins.check_notice_version(_tree(tmp_path))
    assert code == 0
    assert any("matches plugin.json" in line for line in report)


def test_stale_notice_version_fails(tmp_path):
    code, report = check_pins.check_notice_version(
        _tree(tmp_path, notice_version="0.14.0")
    )
    assert code == 1
    assert any("does not match" in line for line in report)


def test_missing_notice_fails_closed(tmp_path):
    code, report = check_pins.check_notice_version(_tree(tmp_path, notice=False))
    assert code == 1
    assert any("NOTICE.md missing" in line for line in report)


def test_missing_plugin_fails_closed(tmp_path):
    code, report = check_pins.check_notice_version(_tree(tmp_path, plugin=False))
    assert code == 1
    assert any("plugin.json missing" in line for line in report)


def test_undeclared_version_fails(tmp_path):
    root = _tree(tmp_path)
    (root / "NOTICE.md").write_text("# NOTICE\n\nNo version line.\n", encoding="utf-8")
    code, report = check_pins.check_notice_version(root)
    assert code == 1
    assert any("does not declare" in line for line in report)
