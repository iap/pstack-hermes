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


def test_audit_reports_unknown_without_remote_default(tmp_path):
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
    (repo / "file.txt").write_text("x", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "file.txt"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "init"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "worktree", "add", "-q", "-b", "feature", str(tmp_path / "feature-wt")],
        check=True,
    )
    result = subprocess.run(
        ["bash", str(AUDIT), str(repo)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert "remote default branch unknown" in result.stderr
    rows = [line for line in result.stdout.splitlines() if "feature-wt" in line]
    assert rows and "unknown" in rows[0]
