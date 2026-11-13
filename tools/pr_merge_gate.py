#!/usr/bin/env python3
"""Pre-merge gate for the bot-review contract (docs/agent/bot-reviews.md).

Green CI is not the merge gate. The repository requires all of:

- CodeRabbit **clean on the current head** — a `skipping` check means *never
  requested*, which is not clean;
- every Qodo finding fixed or answered with evidence;
- every review thread resolved;
- CI green, local gates passing.

This tool checks the machine-readable half: the check rollup, and the unchecked
boxes in the PR body's ``## Bot review (gate)`` section. Thread resolution and
Qodo triage stay human — the tool never claims they are done, only that nothing
machine-visible blocks the merge.

Usage::

    python tools/pr_merge_gate.py 203
    python tools/pr_merge_gate.py 203 --repo iap/pstack-hermes
    python tools/pr_merge_gate.py 203 --json rollup.json --body-file body.md

Exit codes: 0 clean; 1 blocked; 2 the gate could not run.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# A check that finished with one of these is a failure for merge purposes.
FAILING = {
    "FAILURE",
    "ERROR",
    "TIMED_OUT",
    "CANCELLED",
    "STARTUP_FAILURE",
    "ACTION_REQUIRED",
}
# A CodeRabbit verdict in one of these states is *not* clean: `skipping` means
# never requested, `neutral` means it reviewed nothing, and anything unfinished
# is pending.
NOT_CLEAN = {"", "SKIPPED", "NEUTRAL", "PENDING", "QUEUED", "IN_PROGRESS", "REQUESTED", "WAITING"}

BOT_SECTION_RE = re.compile(r"^##\s+Bot review \(gate\).*?$", re.MULTILINE)
NEXT_SECTION_RE = re.compile(r"^##\s+", re.MULTILINE)
UNCHECKED_RE = re.compile(r"^\s*-\s*\[ \]\s*(.+?)\s*$", re.MULTILINE)


def _name(entry: dict) -> str:
    return str(entry.get("name") or entry.get("context") or "")


def _conclusion(entry: dict) -> str:
    return str(entry.get("conclusion") or entry.get("state") or "").upper()


def _status(entry: dict) -> str:
    return str(entry.get("status") or "").upper()


def bot_boxes(body: str) -> list[str]:
    """Unchecked boxes inside the PR body's bot-review section."""
    match = BOT_SECTION_RE.search(body or "")
    if match is None:
        return []
    rest = body[match.end():]
    end = NEXT_SECTION_RE.search(rest)
    section = rest[: end.start()] if end else rest
    return [item for item in UNCHECKED_RE.findall(section)]


def evaluate(rollup: list[dict], body: str) -> list[str]:
    """Return the blocking problems; empty means the machine-checkable gate is clean."""
    problems: list[str] = []
    coderabbit_seen = False

    for entry in rollup or []:
        name = _name(entry)
        conclusion = _conclusion(entry)
        status = _status(entry)

        if "coderabbit" in name.lower():
            coderabbit_seen = True
            if conclusion in NOT_CLEAN or status in {"QUEUED", "IN_PROGRESS", "REQUESTED", "WAITING"}:
                problems.append(
                    "CodeRabbit is not clean on this head "
                    f"(status={status or 'unknown'}, conclusion={conclusion or 'none'}); "
                    "`skipping` means never requested"
                )
            continue

        if conclusion in FAILING:
            problems.append(f"check failed: {name} ({conclusion})")

    if not coderabbit_seen:
        problems.append("no CodeRabbit check on this head; request `@coderabbitai full review`")

    for box in bot_boxes(body):
        problems.append(f"bot-review box unchecked: {box}")
    return problems


def fetch(pr: int, repo: str) -> tuple[list[dict], str]:
    """Read the rollup and body through `gh`, which owns the credentials."""
    proc = subprocess.run(
        ["gh", "pr", "view", str(pr), "--repo", repo, "--json", "statusCheckRollup,body"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout).strip()[:400])
    data = json.loads(proc.stdout)
    return data.get("statusCheckRollup") or [], data.get("body") or ""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("pr", type=int, help="pull request number")
    ap.add_argument("--repo", default="iap/pstack-hermes", help="owner/name (default: this project)")
    ap.add_argument("--json", dest="rollup_file", default="", help="read the rollup from a file")
    ap.add_argument("--body-file", default="", help="read the PR body from a file")
    args = ap.parse_args(argv)

    try:
        if args.rollup_file and args.body_file:
            rollup = json.loads(Path(args.rollup_file).read_text(encoding="utf-8"))
            body = Path(args.body_file).read_text(encoding="utf-8")
        else:
            rollup, body = fetch(args.pr, args.repo)
    except (OSError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"merge-gate: cannot read PR #{args.pr}: {exc}", file=sys.stderr)
        return 2

    problems = evaluate(rollup, body)
    if not problems:
        print(f"PR #{args.pr}: machine-checkable merge gate is clean")
        print("  still human: Qodo triage, thread resolution, local gates")
        return 0

    print(f"PR #{args.pr}: MERGE BLOCKED", file=sys.stderr)
    for problem in problems:
        print(f"  - {problem}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
