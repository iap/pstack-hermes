"""Unresolved VCS conflict markers must not survive into generated output."""

import validate


def test_conflict_markers_detected(tmp_path):
    skill = tmp_path / "skills" / "demo" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(
        "---\nname: demo\ndescription: demo\n---\n"
        "<<<<<<< HEAD\nold line\n=======\nnew line\n>>>>>>> 296badc\n",
        encoding="utf-8",
    )

    rep = validate.Report()
    validate.check_conflict_markers(tmp_path, rep)

    joined = "\n".join(rep.failed)
    assert "SKILL.md:5" in joined
    assert "SKILL.md:9" in joined
    # The setext-underline-shaped `=======` line is deliberately not flagged.
    assert "SKILL.md:7" not in joined


def test_clean_package_and_node_modules_pass(tmp_path):
    skill = tmp_path / "skills" / "demo" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(
        "---\nname: demo\ndescription: demo\n---\nHeading\n=======\n",
        encoding="utf-8",
    )
    vendor = tmp_path / "skills" / "demo" / "node_modules" / "pkg"
    vendor.mkdir(parents=True)
    (vendor / "README.md").write_text("<<<<<<< vendored\n", encoding="utf-8")

    rep = validate.Report()
    validate.check_conflict_markers(tmp_path, rep)

    assert not rep.failed
    assert any("conflict markers: none" in message for message in rep.passed)
