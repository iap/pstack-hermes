"""T11 target selection: shell scripts are in scope, not just markdown.

The worktree-audit.sh transcript note was silently skipped for the package's
entire history because T11 only scanned *.md — this pins the scope.
"""

import convert


def test_t11_targets_include_shell_scripts(tmp_path):
    skills = tmp_path / "skills"
    (skills / "a").mkdir(parents=True)
    (skills / "b").mkdir()
    (skills / "a" / "x.md").write_text("md", encoding="utf-8")
    (skills / "b" / "y.sh").write_text("sh", encoding="utf-8")
    (skills / "b" / "z.txt").write_text("txt", encoding="utf-8")

    targets = [p.name for p in convert.t11_targets(tmp_path)]

    assert targets == ["x.md", "y.sh"]


def test_t11_map_carries_the_worktree_audit_transcript_anchor():
    anchors = [old for old, _new in convert.T11_MAP]
    assert any("Transcripts dir: ~/.cursor/projects/" in a for a in anchors), (
        "the worktree-audit.sh transcript-path anchor was pruned; the package "
        "ships the un-annotated Cursor-only comment again"
    )
