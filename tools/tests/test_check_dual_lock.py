import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_dual_lock  # noqa: E402

check = check_dual_lock.check


def _write(root, bun_cmd, npm_cmd):
    (root / "package.json").write_text(
        json.dumps({"dependencies": {"commander": "15.0.0"}}), encoding="utf-8"
    )
    (root / "bun.lock").write_text(f'"commander": ["commander@{bun_cmd}", ""],\n', encoding="utf-8")
    (root / "package-lock.json").write_text(
        json.dumps({"packages": {"node_modules/commander": {"version": npm_cmd}}}),
        encoding="utf-8",
    )


def test_dual_lock_agree(tmp_path):
    _write(tmp_path, "15.0.0", "15.0.0")
    code, problems = check(tmp_path)
    assert code == 0
    assert problems == []


def test_dual_lock_mismatch(tmp_path):
    _write(tmp_path, "15.0.0", "14.0.0")
    code, problems = check(tmp_path)
    assert code == 1
    assert any("commander" in line for line in problems)
