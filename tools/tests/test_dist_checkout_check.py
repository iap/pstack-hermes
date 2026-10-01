"""The dist checkout check must fail when the attributes rule is absent.

A regression test that only ever passes is worthless: these cases pin the two
failure modes the check exists to catch, so a future edit that weakens it (drops
the CRLF assertion, stops comparing binaries, stages before writing the
attributes file) fails here instead of shipping.
"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import dist_checkout_check as checker  # noqa: E402

ATTRS_NAME = checker.ATTRS_NAME


def _package(tmp_path: Path, attrs: str | None) -> Path:
    """Build a minimal dist-like package, optionally with an attributes rule."""
    pkg = tmp_path / "pkg"
    (pkg / "skills" / "demo").mkdir(parents=True)
    (pkg / "skills" / "demo" / "SKILL.md").write_text(
        "---\nname: demo\ndescription: d\n---\nbody\n", encoding="utf-8", newline=""
    )
    (pkg / "config").mkdir()
    (pkg / "config" / "models.json").write_text('{"a": 1}\n', encoding="utf-8", newline="")
    (pkg / "assets").mkdir()
    # A real PNG header so git's own binary sniffing sees a genuine binary.
    (pkg / "assets" / "logo.png").write_bytes(
        bytes.fromhex("89504e470d0a1a0a0000000d49484452")
        + b"\x00\x00\x00\x10\x00\x00\x00\x10\x08\x06\x00\x00\x00"
        + b"\x8f\x5f\x3f\x8c\x00\x00\x00\x0aIDATx\x9cc\x00\x01"
        + b"\x00\x00\x05\x00\x01\x0d\x0a-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    if attrs is not None:
        (pkg / ATTRS_NAME).write_text(attrs, encoding="utf-8", newline="")
    return pkg


def _run(package: Path, attrs_source: Path, monkeypatch) -> int:
    monkeypatch.setattr(checker, "ATTRS_SOURCE", attrs_source)
    return checker.main(["--package", str(package)])


def test_clean_tree_passes(tmp_path, monkeypatch):
    attrs = tmp_path / "attrs"
    attrs.write_text("* text=auto eol=lf\n*.png binary\n", encoding="utf-8", newline="")
    pkg = _package(tmp_path, None)
    assert _run(pkg, attrs, monkeypatch) == 0


def test_checker_reports_crlf_when_the_rule_does_not_pin_lf(tmp_path, monkeypatch, capsys):
    """The pre-fix state must be reported as CRLF, on every host.

    Asserted via the file's actual bytes rather than by relying on the host's
    own autocrlf behaviour: git ignores core.autocrlf=true on POSIX, so on a
    Linux runner a checkout comes out LF whatever the attributes say. The checker
    solves that with a simulated-consumer attributesFile, but a test that depends
    on the *runner* converting line endings would pass vacuously on Linux - which
    is exactly how this case failed its first CI run.
    """
    attrs = tmp_path / "attrs"
    # A real, wrong rule rather than an empty file: `eol=crlf` is what a consumer
    # default degrades to, so the checkout genuinely comes back CRLF everywhere.
    attrs.write_text("* text=auto eol=crlf\n", encoding="utf-8", newline="")
    pkg = _package(tmp_path, None)
    assert _run(pkg, attrs, monkeypatch) == 1
    assert "CRLF" in capsys.readouterr().err


def test_empty_rule_leaves_eol_unspecified(tmp_path, monkeypatch):
    """`git check-attr` is the deterministic half of the contract.

    The published rule must make `eol` explicit for every text file. This does
    not depend on any conversion actually happening, so it holds identically on
    Windows and Linux - which the byte-level assertions above cannot.
    """
    import subprocess

    good = _package(tmp_path, None)
    (good / checker.ATTRS_NAME).write_text(
        "* text=auto eol=lf\n*.png binary\n", encoding="utf-8", newline=""
    )
    bad = tmp_path / "pkg-bad"
    bad.mkdir()
    (bad / "a.md").write_text("x\n", encoding="utf-8", newline="")
    (bad / checker.ATTRS_NAME).write_text("", encoding="utf-8", newline="")

    def eol_for(pkg: Path) -> str:
        subprocess.run(["git", "init", "-q", str(pkg)], capture_output=True, check=False)
        out = subprocess.run(
            ["git", "-C", str(pkg), "check-attr", "eol", "--", "a.md"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout
        return out.strip().rsplit(":", 1)[-1].strip()

    assert eol_for(good) == "lf"
    assert eol_for(bad) == "unspecified"


def test_png_marked_text_is_caught(tmp_path, monkeypatch):
    # The reason *.png is pinned binary: without it, a `text` rule makes git
    # rewrite the bytes and the checkout no longer matches the staged tree.
    attrs = tmp_path / "attrs"
    attrs.write_text("* text=auto eol=lf\n*.png text\n", encoding="utf-8", newline="")
    pkg = _package(tmp_path, None)
    assert _run(pkg, attrs, monkeypatch) == 1


def test_missing_package_is_tool_error(tmp_path, monkeypatch):
    attrs = tmp_path / "attrs"
    attrs.write_text("* text=auto eol=lf\n", encoding="utf-8", newline="")
    assert _run(tmp_path / "absent", attrs, monkeypatch) == 2


def test_shipped_rule_matches_the_asset_the_publisher_copies():
    # The publisher copies tools/assets/dist.gitattributes verbatim; if that file
    # is ever edited by hand in a way that stops pinning LF, say so here.
    body = checker.ATTRS_SOURCE.read_text(encoding="utf-8")
    assert "eol=lf" in body
    assert "*.png binary" in body


def test_checker_does_not_mutate_the_package(tmp_path, monkeypatch):
    attrs = tmp_path / "attrs"
    attrs.write_text("* text=auto eol=lf\n", encoding="utf-8", newline="")
    pkg = _package(tmp_path, None)
    before = subprocess.run(
        ["git", "init", "-q", str(pkg)], capture_output=True, text=True, check=False
    )
    assert before.returncode == 0
    head = subprocess.run(
        ["git", "-C", str(pkg), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    _run(pkg, attrs, monkeypatch)
    after = subprocess.run(
        ["git", "-C", str(pkg), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    assert head == after