"""Encoding checks ignore generated dependency installs inside the package tree."""

import validate


def test_encoding_check_skips_generated_node_modules(tmp_path):
    vendor = tmp_path / "skills" / "poteto-mode" / "scripts" / "node_modules" / "pkg"
    vendor.mkdir(parents=True)
    (vendor / "README.md").write_text("third-party readme\r\n", encoding="utf-8")
    skill = tmp_path / "skills" / "demo" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: demo\ndescription: demo\n---\n", encoding="utf-8")

    rep = validate.Report()
    validate.check_encoding(tmp_path, rep)

    assert not rep.failed
    assert any("no CRLF" in message and "1 text files" in message for message in rep.passed)
