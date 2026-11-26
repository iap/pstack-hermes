import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / "scripts" / "worktree-audit.sh"


def _audit(tmp_path, trunk: str):
    repo = tmp_path / trunk
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "symbolic-ref",
            "refs/remotes/origin/HEAD",
            f"refs/remotes/origin/{trunk}",
        ],
        check=True,
    )
    return subprocess.run(
        ["bash", str(AUDIT), str(repo)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_audit_uses_remote_default_master(tmp_path):
    result = _audit(tmp_path, "master")
    assert "could not fetch origin/master" in result.stderr
    assert "origin/main" not in result.stderr
    assert result.stdout.startswith("SIZE\tAGE\tMERGED")


def test_audit_keeps_remote_default_main(tmp_path):
    result = _audit(tmp_path, "main")
    assert "could not fetch origin/main" in result.stderr
    assert result.stdout.startswith("SIZE\tAGE\tMERGED")
