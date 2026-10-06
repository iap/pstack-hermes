#!/usr/bin/env python3
"""Assert every UPSTREAM_PIN declaration agrees, and is well-formed.

AGENTS.md and CONTRIBUTING.md both state the rule - the pin must stay in
lock-step across ci.yml / release.yml / publish-dist.yml /
upstream-drift-watch.yml - but nothing enforced it. A bump that missed one file
would ship a package built from a pin that CI never validated, and only a code
review would notice. This gate makes the documented rule machine-checked and
exists specifically to de-risk the re-pin procedure in
docs/RUNBOOK-upstream-drift.md.

Exit codes: 0 all declarations agree and are well-formed; 1 mismatch or
malformed; 2 unreadable input.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Every workflow that MUST declare the pin. Adding a workflow that builds or
# describes a build from the pin means adding it here (and to the runbook).
REQUIRED_DECLARERS = (
    "ci.yml",
    "release.yml",
    "publish-dist.yml",
    "upstream-drift-watch.yml",
)

# `UPSTREAM_PIN: <value>` at the start of a YAML mapping entry. References like
# `${{ env.UPSTREAM_PIN }}` do not match because the value must be token-shaped.
DECL_RE = re.compile(r"^\s*UPSTREAM_PIN:\s*(\S+)\s*$", re.MULTILINE)
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def declarations(root: Path = ROOT) -> list[tuple[str, str]]:
    """Return (filename, value) for every UPSTREAM_PIN declaration in workflows."""
    out: list[tuple[str, str]] = []
    for wf in sorted((root / ".github" / "workflows").glob("*.y*ml")):
        text = wf.read_text(encoding="utf-8")
        for match in DECL_RE.finditer(text):
            out.append((wf.name, match.group(1)))
    return out


def check(root: Path = ROOT) -> tuple[int, list[str]]:
    """Run the check; return (exit_code, report lines)."""
    workflows_dir = root / ".github" / "workflows"
    if not workflows_dir.is_dir():
        return 2, [f"error: no workflows directory at {workflows_dir}"]

    decls = declarations(root)
    if not decls:
        return 2, ["error: no UPSTREAM_PIN declaration found in any workflow"]

    report: list[str] = []
    problems: list[str] = []

    by_file: dict[str, list[str]] = {}
    for name, value in decls:
        by_file.setdefault(name, []).append(value)

    for name in REQUIRED_DECLARERS:
        values = by_file.get(name)
        if not values:
            problems.append(f"{name}: does not declare UPSTREAM_PIN")
        elif len(values) > 1:
            problems.append(f"{name}: declares UPSTREAM_PIN {len(values)} times")

    distinct = sorted({v for _, v in decls})
    for name, values in sorted(by_file.items()):
        report.append(f"  {name}: {', '.join(values)}")
    if len(distinct) > 1:
        problems.append(
            "UPSTREAM_PIN values disagree across workflows: " + ", ".join(distinct)
        )
    elif not SHA_RE.match(distinct[0]):
        problems.append(
            f"UPSTREAM_PIN is not a full lowercase 40-char SHA: {distinct[0]!r}"
        )

    if problems:
        report.extend(f"FAIL: {p}" for p in problems)
        return 1, report
    return 0, report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="check_pins.py", description=__doc__)
    ap.add_argument("--root", type=Path, default=ROOT, help="repository root")
    args = ap.parse_args(argv)
    code, report = check(args.root)
    stream = sys.stderr if code else sys.stdout
    for line in report:
        print(line, file=stream)
    if code == 0:
        print("upstream pin: in lock-step across all workflows")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
