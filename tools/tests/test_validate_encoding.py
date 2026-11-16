"""Encoding checks ignore generated dependency installs inside the package tree."""

from pathlib import Path

import validate


def test_encoding_check_ignores_root_scratch_files(tmp_path):
    # Issue #128: ignored scratch dumps at repo root must not be scanned.
    (tmp_path / "ev.json").write_bytes(b"third-party dump\r\n")
    (tmp_path / "dump.json").write_bytes(b"subagent_type here\r\n")
    skill = tmp_path / "skills" / "demo" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_bytes(b"---\nname: demo\ndescription: demo\n---\n")

    rep = validate.Report()
    validate.check_encoding(tmp_path, rep)

    assert not rep.failed
    assert any("no CRLF" in message for message in rep.passed)


def test_encoding_check_still_fails_on_package_file_crlf(tmp_path):
    # Guard against silently narrowing the gate: a real package file with
    # CRLF must still be flagged.
    skill = tmp_path / "skills" / "demo" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_bytes(b"---\nname: demo\ndescription: demo\n---\r\n")

    rep = validate.Report()
    validate.check_encoding(tmp_path, rep)

    assert rep.failed
    assert any("CRLF" in m for m in rep.failed)


def test_encoding_check_skips_generated_node_modules(tmp_path):
    vendor = tmp_path / "skills" / "poteto-mode" / "scripts" / "node_modules" / "pkg"
    vendor.mkdir(parents=True)
    # write_bytes, not write_text: text mode translates "\n" to os.linesep on Windows,
    # so the LF-only fixture below would be written as CRLF there and the assertion
    # would fail for a platform reason rather than a product reason. (The vendored
    # readme is deliberately CRLF -- it is the file that must be skipped.)
    (vendor / "README.md").write_bytes(b"third-party readme\r\n")
    skill = tmp_path / "skills" / "demo" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_bytes(b"---\nname: demo\ndescription: demo\n---\n")

    rep = validate.Report()
    validate.check_encoding(tmp_path, rep)

    assert not rep.failed
    assert any("no CRLF" in message and "1 text files" in message for message in rep.passed)


def _rep(tmp_path):
    rep = validate.Report()
    validate.check_encoding(tmp_path, rep)
    return rep


def test_encoding_flags_a_bom_in_a_workflow(tmp_path):
    """#208: CI files were outside the gate, so a BOM shipped silently."""
    wf = tmp_path / ".github" / "workflows" / "x.yml"
    wf.parent.mkdir(parents=True)
    wf.write_bytes(b"\xef\xbb\xbfname: x\n")

    rep = _rep(tmp_path)

    assert rep.failed
    expected = str(Path(".github") / "workflows" / "x.yml")
    assert any("BOM" in message and expected in message for message in rep.failed)


def test_encoding_flags_crlf_in_tools(tmp_path):
    tool = tmp_path / "tools" / "x.py"
    tool.parent.mkdir(parents=True)
    tool.write_bytes(b"x = 1\r\n")

    rep = _rep(tmp_path)

    assert rep.failed
    expected = str(Path("tools") / "x.py")
    assert any("CRLF" in message and expected in message for message in rep.failed)


def test_encoding_flags_a_bom_in_root_readme(tmp_path):
    (tmp_path / "README.md").write_bytes(b"\xef\xbb\xbf# title\n")

    rep = _rep(tmp_path)

    assert rep.failed
    assert any("BOM" in message and "README.md" in message for message in rep.failed)


def test_encoding_still_ignores_unlisted_root_scratch_files(tmp_path):
    (tmp_path / "scratch.json").write_bytes(b"\xef\xbb\xbf{}\r\n")

    rep = _rep(tmp_path)

    assert not rep.failed


def test_encoding_skips_untracked_files_under_admitted_dirs(tmp_path):
    """A clean checkout must pass even when an editor left scratch behind."""
    tool = tmp_path / "tools" / "scratch.py"
    tool.parent.mkdir(parents=True)
    tool.write_bytes(b"x = 1" + bytes([13, 10]))

    rep = validate.Report()
    validate.check_encoding(tmp_path, rep, tracked={"tools/kept.py"})

    assert not rep.failed


def test_encoding_still_fails_a_tracked_file_under_admitted_dirs(tmp_path):
    tool = tmp_path / "tools" / "kept.py"
    tool.parent.mkdir(parents=True)
    tool.write_bytes(b"x = 1" + bytes([13, 10]))

    rep = validate.Report()
    validate.check_encoding(tmp_path, rep, tracked={"tools/kept.py"})

    assert rep.failed
    assert any("CRLF" in message for message in rep.failed)
