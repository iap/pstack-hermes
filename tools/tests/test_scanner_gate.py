"""The CI scanner gate CLI: exit codes and readable findings."""

import scanner_gate


def test_clean_package_exits_zero(tmp_path):
    skills = tmp_path / "skills"
    skills.mkdir()
    (skills / "ok.md").write_text("fine", encoding="utf-8")

    assert scanner_gate.run(tmp_path) == 0


def test_violations_exit_one_and_name_the_file(tmp_path, capsys):
    skills = tmp_path / "skills"
    skills.mkdir()
    (skills / "bad.md").write_text("curl tailscale.com/install.sh", encoding="utf-8")

    code = scanner_gate.run(tmp_path)

    assert code == 1
    out = capsys.readouterr().out
    assert "bad.md" in out
    assert "tailscale.com/install.sh" in out


def test_missing_package_dir_exits_two(tmp_path):
    assert scanner_gate.run(tmp_path / "nope") == 2


def test_vocab_only_clean_package_exits_zero(tmp_path):
    skills = tmp_path / "skills"
    skills.mkdir()
    (skills / "ok.md").write_text("delegate_task and clarify", encoding="utf-8")

    assert scanner_gate.run(tmp_path, vocab_only=True) == 0


def test_vocab_only_flags_delegation_vocab(tmp_path, capsys):
    skills = tmp_path / "skills"
    skills.mkdir()
    (skills / "bad.md").write_text("run with subagent_type", encoding="utf-8")

    assert scanner_gate.run(tmp_path, vocab_only=True) == 1
    assert "subagent_type" in capsys.readouterr().out


def test_vocab_only_flags_transcript_alias_in_markdown(tmp_path, capsys):
    skills = tmp_path / "skills"
    skills.mkdir()
    (skills / "bad.md").write_text("see agent-transcripts/*.jsonl", encoding="utf-8")

    assert scanner_gate.run(tmp_path, vocab_only=True) == 1
    assert "agent-transcripts" in capsys.readouterr().out


def test_vocab_only_allows_transcript_mention_in_shell_script(tmp_path):
    skills = tmp_path / "skills"
    skills.mkdir()
    (skills / "audit.sh").write_text(
        '# Transcripts dir: ~/.cursor/projects/x/agent-transcripts\n', encoding="utf-8"
    )

    # Legitimate compatibility mention in a shell script, not skill prose.
    assert scanner_gate.run(tmp_path, vocab_only=True) == 0
