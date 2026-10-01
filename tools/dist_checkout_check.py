#!/usr/bin/env python3
"""Regression check: a checkout of the DIST tree must be LF-only, with binaries intact.

Why this exists
---------------
The package contract is LF-only (see ``tools/validate.py::check_encoding``), and
the dist repo is what ``hermes plugins install iap/pstack`` actually clones. The
``build`` CI job validates the *source* ``pstack/`` directory, where files are LF
because ``tools/convert.py`` wrote them that way. That job is structurally
incapable of catching a line-ending or binary-asset regression introduced by the
publish step, because it never constructs a checkout of the published tree on a
consumer-like configuration.

So this check does the one thing nothing else does: build a throwaway git repo
from a staged dist tree with ``core.autocrlf=true``, the default on Windows, and
assert that what a consumer would receive is byte-correct.

The attributes rule lives in ``tools/assets/dist.gitattributes`` and is copied to
both the staged dist tree and this check, so the publisher and the regression
test cannot drift apart. ``--package`` may be used to verify a real checkout.

Exit codes:
  0  every text file checked out LF, every binary byte-identical
  1  a text file is CRLF, or a binary was altered
  2  the input could not be read or git was unavailable
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ATTRS_NAME = ".gitattributes"
ATTRS_SOURCE = SCRIPT_DIR / "assets" / "dist.gitattributes"

# Reuse the converter's single definition of "this file is text" so the checkout
# check and the build-time encoding gate agree on the file set.
sys.path.insert(0, str(SCRIPT_DIR))
from convert import TEXT_EXTS  # noqa: E402

TEXT_NAMES = {ATTRS_NAME, ".gitignore", ".build-provenance.txt"}
BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".woff", ".woff2"}


def run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def is_text_file(rel: str) -> bool:
    p = Path(rel)
    return p.suffix.lower() in TEXT_EXTS or p.name in TEXT_NAMES


def is_binary_file(rel: str) -> bool:
    return Path(rel).suffix.lower() in BINARY_SUFFIXES


def stage_tree(package: Path, dest: Path) -> None:
    """Copy the package tree into ``dest`` the way the publisher stages it."""
    for item in package.iterdir():
        if item.name == ".git":
            continue
        target = dest / item.name
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)
    shutil.copy2(ATTRS_SOURCE, dest / ATTRS_NAME)


def clone_like_consumer(staged: Path, workdir: Path) -> Path:
    """Materialize a checkout of the staged tree with autocrlf=true.

    This mirrors what ``hermes plugins install`` does: a git clone on a machine
    whose default is core.autocrlf=true (Windows).

    The attributes file is applied inside the repo *before* ``git add`` so the
    index stores LF, exactly as the publisher stages it. Adding first would let
    a consumer-default autocrlf setting rewrite the blobs during ``add``.
    """
    repo = workdir / "dist-repo"
    repo.mkdir()
    if run_git(["init", "-q"], repo).returncode != 0:
        raise RuntimeError("git init failed")
    run_git(["config", "user.email", "ci@example.invalid"], repo)
    run_git(["config", "user.name", "ci"], repo)
    shutil.copy2(ATTRS_SOURCE, repo / ATTRS_NAME)
    for item in staged.iterdir():
        if item.name == ATTRS_NAME:
            continue
        target = repo / item.name
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)
    if run_git(["add", "-A"], repo).returncode != 0:
        raise RuntimeError("git add failed")
    _commit = run_git(["commit", "-q", "-m", "staged dist tree"], repo)
    if _commit.returncode != 0:
        raise RuntimeError(f"git commit failed: {_commit.stderr.strip() or _commit.stdout.strip()}")

    # A separate clone, so the checkout is produced by git rather than left as
    # the staging copy (which would trivially be LF and prove nothing).
    clone = workdir / "consumer"
    res = run_git(["clone", "-q", str(repo), str(clone)], workdir)
    if res.returncode != 0:
        raise RuntimeError(f"git clone failed: {res.stderr.strip()}")
    run_git(["config", "core.autocrlf", "true"], clone)
    # Force every tracked file back through checkout so the attributes rule,
    # not the staging bytes, decides the working-tree form.
    run_git(["checkout", "-f", "HEAD", "--", "."], clone)
    return clone


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="dist_checkout_check.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "--package",
        type=Path,
        required=True,
        help="dist tree to verify (usually the staged copy the publisher builds)",
    )
    args = ap.parse_args(argv)

    package: Path = args.package
    if not package.is_dir():
        print(f"error: package dir not found: {package}", file=sys.stderr)
        return 2
    if not ATTRS_SOURCE.is_file():
        print(f"error: {ATTRS_SOURCE} not found", file=sys.stderr)
        return 2
    if shutil.which("git") is None:
        print("error: git is not installed or not in PATH", file=sys.stderr)
        return 2

    workdir = Path(tempfile.mkdtemp(prefix="pstack-dist-checkout-"))
    try:
        staged = workdir / "staged"
        staged.mkdir()
        stage_tree(package, staged)
        source_hashes = {
            str(p.relative_to(staged)).replace("\\", "/"): sha256(p)
            for p in staged.rglob("*")
            if p.is_file()
        }

        clone = clone_like_consumer(staged, workdir)

        tracked = run_git(["ls-files"], clone).stdout.split()
        if not tracked:
            print("error: the consumer checkout tracked no files", file=sys.stderr)
            return 2

        crlf: list[str] = []
        mangled: list[str] = []
        missing: list[str] = []
        checked_text = 0
        checked_binary = 0
        for rel in tracked:
            target = clone / rel
            if not target.is_file():
                missing.append(rel)
                continue
            before = source_hashes.get(rel)
            if before is None:
                continue
            if is_text_file(rel):
                checked_text += 1
                if b"\r\n" in target.read_bytes():
                    crlf.append(rel)
            else:
                # Every non-text tracked file must survive the checkout byte-for-byte,
                # whether or not it is a format git happens to sniff as binary. This is
                # the assertion that would catch a future `text=auto` overreach; a
                # format-specific suffix list would not, because git already protects
                # the formats it can sniff.
                checked_binary += 1
                if sha256(target) != before:
                    mangled.append(rel)

        failures: list[str] = []
        if crlf:
            failures.append(
                f"{len(crlf)} text file(s) checked out as CRLF under autocrlf=true: "
                f"{crlf[:10]}"
            )
        if missing:
            failures.append(f"{len(missing)} tracked file(s) absent from the checkout: {missing[:10]}")
        if mangled:
            failures.append(
                f"{len(mangled)} binary file(s) altered by the checkout: {mangled[:10]}"
            )

        if failures:
            for failure in failures:
                print(f"FAIL: {failure}", file=sys.stderr)
            print(
                f"\ndist-checkout: {len(failures)} problem(s) "
                f"({checked_text} text, {checked_binary} binary checked)",
                file=sys.stderr,
            )
            return 1

        print(
            f"dist-checkout: consumer checkout is clean "
            f"({checked_text} text LF-only, {checked_binary} binary byte-identical) "
            f"under autocrlf=true"
        )
        return 0
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())