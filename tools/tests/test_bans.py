"""The shared banned-construct scanner: one source of truth for validate + CI gate."""

import bans


def test_security_bans_match_any_decodable_extension(tmp_path):
    skills = tmp_path / "skills"
    skills.mkdir()
    (skills / "evil.ts").write_text("fetch('http://127.0.0.1:4173');", encoding="utf-8")

    violations = bans.find_violations(tmp_path)

    assert any("evil.ts" in v and "127.0.0.1:4173" in v for v in violations)


def test_vocab_bans_apply_only_to_the_hermes_facing_surface(tmp_path):
    for rel in ("agents/p.md", ".cursor-plugin/plugin.json"):
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("uses subagent_type", encoding="utf-8")
    (tmp_path / ".build-provenance.txt").write_text("fixed subagent_type", encoding="utf-8")
    skills = tmp_path / "skills"
    skills.mkdir()
    (skills / "s.md").write_text("uses subagent_type", encoding="utf-8")

    flagged = [v for v in bans.find_violations(tmp_path) if "subagent_type" in v]

    assert len(flagged) == 1
    assert "skills/s.md" in flagged[0]


def test_clean_tree_has_no_violations(tmp_path):
    skills = tmp_path / "skills"
    skills.mkdir()
    (skills / "ok.md").write_text("hello hermes", encoding="utf-8")

    assert bans.find_violations(tmp_path) == []


def test_undecodable_binary_files_are_skipped(tmp_path):
    (tmp_path / "blob.bin").write_bytes(b"\xff\xfe" + b"tailscale.com/install.sh")

    assert bans.find_violations(tmp_path) == []
