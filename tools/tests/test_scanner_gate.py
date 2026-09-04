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
