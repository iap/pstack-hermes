#!/usr/bin/env python3
"""Check a pull-request description against the tree that PR proposes.

Advisory by design: this reports contradictions, it does not enforce them. The
enforcing gate is the CI `build` job. Exit codes:

  0  every machine-checkable claim in the PR body holds (or there was nothing
     to check - a PR that does not touch the generated package)
  1  a checked box with no evidence pasted
  2  the input could not be read/parsed at all

Usage:
  pr_checklist.py <pr-body-file>
  pr_checklist.py --help

Retired with the standalone refactor (issue #156): the provenance-block
pin comparison died with the upstream converter. Only the box-evidence
check remains.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

CHECKED_BOX_RE = re.compile(r"^\s*[-*]\s*\[x\]\s*(.+?)\s*$", re.MULTILINE | re.IGNORECASE)
# Evidence is either an explicit "Evidence:" label or a fenced code block
# (which is what .github/PULL_REQUEST_TEMPLATE.md actually asks for).
EVIDENCE_HINT_RE = re.compile(r"evidence\s*:|^\s*```", re.IGNORECASE | re.MULTILINE)


PLACEHOLDER_RE = re.compile(r"<[^>]*>|\b(your|fill|todo|tbd)\b", re.IGNORECASE)


def strip_html_comments(body: str) -> str:
    """Remove <!-- ... --> blocks. The template embeds its instructions as HTML
    comments, and a checked box plus its placeholder output live inside those
    comments in the template itself - not a contributor claim."""
    return re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)


def check_box_evidence(body: str) -> list[str]:
    """A checked box with no pasted evidence proves nothing - the template says
    so itself. Flag every checked box whose own section carries no evidence."""
    problems: list[str] = []
    lines = body.splitlines()
    for i, line in enumerate(lines):
        m = CHECKED_BOX_RE.match(line)
        if not m:
            continue
        # Scan forward until the next checkbox or heading: that window is this
        # box's own evidence slot. If it ends without an evidence marker (or at
        # the next checkbox/heading immediately), the box is bare.
        found = False
        for follow in lines[i + 1 :]:
            if CHECKED_BOX_RE.match(follow) or follow.strip().startswith("#"):
                break
            if EVIDENCE_HINT_RE.search(follow):
                found = True
                break
        if not found:
            problems.append(
                f"checked box has no evidence pasted: {m.group(1)[:70]!r}"
            )
    return problems


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(
        prog="pr_checklist.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("body", type=Path, help="PR description file ('-' for stdin)")
    args = ap.parse_args(argv)

    if str(args.body) == "-":
        body = sys.stdin.read()
    else:
        if not args.body.is_file():
            print(f"error: PR body file not found: {args.body}", file=sys.stderr)
            return 2
        body = args.body.read_text(encoding="utf-8", errors="replace")

    failures: list[str] = []
    notes: list[str] = []
    # Evidence is only meaningful for the Verification section. Boxes elsewhere
    # (e.g. "Affected surface") are scope declarations, not claims backed by
    # pasted output, so requiring evidence for them would be noise.
    verification_only = "--all-boxes" not in argv


    body_wo_comments = strip_html_comments(body)
    if not verification_only:
        failures.extend(check_box_evidence(body_wo_comments))
    else:
        section = re.search(r"^##\s+Verification\b(.*?)(?=^##\s|\Z)",
                            body_wo_comments, re.MULTILINE | re.DOTALL)
        if section:
            failures.extend(check_box_evidence(section.group(1)))
        else:
            notes.append("no '## Verification' section found; box-evidence check skipped")

    for note in notes:
        print(f"note: {note}")
    for failure in failures:
        print(f"FAIL: {failure}", file=sys.stderr)

    if failures:
        print(f"\npr-checklist: {len(failures)} contradiction(s)", file=sys.stderr)
        return 1
    print("pr-checklist: no contradictions found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
