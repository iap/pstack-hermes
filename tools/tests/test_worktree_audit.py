import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / "scripts" / "worktree-audit.sh"


def _audit(tmp_path, trunk: str, remote: str = "origin"):
    repo = tmp_path / f"{remote}-{trunk}"
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    if remote != "origin":
        subprocess.run(
            ["git", "-C", str(repo), "remote", "add", remote, str(tmp_path / "upstream.git")],
            check=True,
        )
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "symbolic-ref",
            f"refs/remotes/{remote}/HEAD",
            f"refs/remotes/{remote}/{trunk}",
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


def test_audit_uses_named_remote(tmp_path):
    result = _audit(tmp_path, "trunk", "upstream")
    assert "could not fetch upstream/trunk" in result.stderr
    assert "origin" not in result.stderr
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


def _fork_tree(tmp_path):
    repo = tmp_path / "fork-repo"
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
    (repo / "file.txt").write_text("x", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "file.txt"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "init"], check=True)
    subprocess.run(["git", "-C", str(repo), "remote", "add", "upstream", str(tmp_path / "upstream.git")], check=True)
    subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", str(tmp_path / "origin.git")], check=True)
    trunk_branch = subprocess.check_output(
        ["git", "-C", str(repo), "symbolic-ref", "--short", "HEAD"], text=True
    ).strip()
    subprocess.run(["git", "-C", str(repo), "config", f"branch.{trunk_branch}.remote", "upstream"], check=True)
    wt = tmp_path / "feature-wt"
    subprocess.run(["git", "-C", str(repo), "worktree", "add", "-q", "-b", "feature", str(wt)], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "symbolic-ref", "refs/remotes/upstream/HEAD", "refs/remotes/upstream/main"],
        check=True,
    )
    return repo, wt


def test_audit_preserves_slash_named_remote(tmp_path):
    repo = tmp_path / "slash-repo"
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "remote", "add", "team/upstream", str(tmp_path / "upstream.git")], check=True)
    branch = subprocess.check_output(
        ["git", "-C", str(repo), "symbolic-ref", "--short", "HEAD"], text=True
    ).strip()
    subprocess.run(["git", "-C", str(repo), "config", f"branch.{branch}.remote", "team/upstream"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "symbolic-ref", "refs/remotes/team/upstream/HEAD", "refs/remotes/team/upstream/trunk"],
        check=True,
    )
    result = subprocess.run(["bash", str(AUDIT), str(repo)], capture_output=True, text=True, check=False)

    assert "could not fetch team/upstream/trunk" in result.stderr


def test_audit_invoked_from_linked_worktree_uses_main_upstream(tmp_path):
    repo, wt = _fork_tree(tmp_path)
    subprocess.run(["git", "-C", str(wt), "config", "branch.feature.remote", "origin"], check=True)

    result = subprocess.run(["bash", str(AUDIT), str(wt)], capture_output=True, text=True, check=False)

    assert "could not fetch upstream/main" in result.stderr


def test_audit_checks_feature_push_remote_separately(tmp_path):
    repo, wt = _fork_tree(tmp_path)
    subprocess.run(["git", "-C", str(wt), "config", "branch.feature.remote", "origin"], check=True)
    feature_sha = subprocess.check_output(["git", "-C", str(wt), "rev-parse", "HEAD"], text=True).strip()
    subprocess.run(["git", "-C", str(repo), "update-ref", "refs/remotes/origin/feature", feature_sha], check=True)

    result = subprocess.run(["bash", str(AUDIT), str(repo)], capture_output=True, text=True, check=False)

    rows = [line for line in result.stdout.splitlines() if "feature-wt" in line]
    assert rows and "\tpushed\t" in rows[0]


def test_audit_checks_feature_on_trunk_remote(tmp_path):
    repo, wt = _fork_tree(tmp_path)
    feature_sha = subprocess.check_output(["git", "-C", str(wt), "rev-parse", "HEAD"], text=True).strip()
    subprocess.run(["git", "-C", str(repo), "update-ref", "refs/remotes/upstream/feature", feature_sha], check=True)

    result = subprocess.run(["bash", str(AUDIT), str(repo)], capture_output=True, text=True, check=False)

    rows = [line for line in result.stdout.splitlines() if "feature-wt" in line]
    assert rows and "\tpushed\t" in rows[0]


def test_audit_handles_remote_name_with_hash(tmp_path):
    repo = tmp_path / "hash-repo"
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "remote", "add", "team#upstream", str(tmp_path / "upstream.git")], check=True)
    branch = subprocess.check_output(
        ["git", "-C", str(repo), "symbolic-ref", "--short", "HEAD"], text=True
    ).strip()
    subprocess.run(["git", "-C", str(repo), "config", f"branch.{branch}.remote", "team#upstream"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "symbolic-ref", "refs/remotes/team#upstream/HEAD", "refs/remotes/team#upstream/trunk"],
        check=True,
    )

    result = subprocess.run(["bash", str(AUDIT), str(repo)], capture_output=True, text=True, check=False)

    assert "could not fetch team#upstream/trunk" in result.stderr


def test_audit_handles_detached_main_worktree(tmp_path):
    repo = tmp_path / "detached-repo"
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
    (repo / "file.txt").write_text("x", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "file.txt"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "init"], check=True)
    subprocess.run(["git", "-C", str(repo), "checkout", "--detach", "-q"], check=True)
    subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", str(tmp_path / "origin.git")], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/master"],
        check=True,
    )

    result = subprocess.run(["bash", str(AUDIT), str(repo)], capture_output=True, text=True, check=False)

    assert result.stdout.startswith("SIZE\tAGE\tMERGED")
    assert "unbound variable" not in result.stderr
