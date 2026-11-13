#!/usr/bin/env python3
"""Pre-merge gate for the bot-review contract (docs/agent/bot-reviews.md).

Green CI is not the merge gate. The repository requires all of:

- CodeRabbit **clean on the current head** â€” a `skipping` check means *never
  requested*, which is not clean;
- every Qodo finding fixed or answered with evidence;
- every review thread resolved;
- CI green, local gates passing.

This tool checks the machine-readable half: the check runs, and the unchecked
boxes in the PR body's ``## Bot review (gate)`` section. Thread resolution and
Qodo triage stay human â€” the tool never claims they are done, only that nothing
machine-visible blocks the merge.

Provenance matters: a check *named* CodeRabbit proves nothing, because a
PR-controlled workflow can publish a job with that name. The verdict is only
counted when GitHub reports the check run's app as ``coderabbitai``.

Usage::

    python tools/pr_merge_gate.py 203
    python tools/pr_merge_gate.py 203 --repo iap/pstack-hermes
    python tools/pr_merge_gate.py 203 --json check-runs.json --body-file body.md

Exit codes: 0 clean; 1 blocked; 2 the gate could not run.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# GitHub's app slug for CodeRabbit. A matching check *name* is not proof.
CODERABBIT_APP = "coderabbitai"

# A finished check with one of these conclusions fails the gate.
FAILING = {
    "FAILURE",
    "ERROR",
    "TIMED_OUT",
    "CANCELLED",
    "STARTUP_FAILURE",
    "ACTION_REQUIRED",
}
# A check still in one of these states has not produced a verdict yet.
UNFINISHED = {"QUEUED", "IN_PROGRESS", "WAITING", "REQUESTED", "PENDING", "EXPECTED"}
# A CodeRabbit verdict in one of these states is not clean: `skipping` means
# never requested, `neutral` means it reviewed nothing.
NOT_CLEAN = {"", "SKIPPED", "NEUTRAL"}

BOT_SECTION_RE = re.compile(r"^##\s+Bot review \(gate\).*?$", re.MULTILINE)
NEXT_SECTION_RE = re.compile(r"^##\s+", re.MULTILINE)
UNCHECKED_RE = re.compile(r"^\s*-\s*\[ \]\s*(.+?)\s*$", re.MULTILINE)


def _name(entry: dict) -> str:
    return str(entry.get("name") or entry.get("context") or "")


def _status(entry: dict) -> str:
    return str(entry.get("status") or "").upper()


def _conclusion(entry: dict) -> str:
    # Status contexts (the legacy commit-status API) carry `state` instead.
    return str(entry.get("conclusion") or entry.get("state") or "").upper()


def _app(entry: dict) -> str:
    app = entry.get("app")
    return str(app.get("slug") or "") if isinstance(app, dict) else ""


def bot_boxes(body: str) -> list[str] | None:
    """Unchecked boxes in the bot-review section, or None when the section is absent."""
    match = BOT_SECTION_RE.search(body or "")
    if match is None:
        return None
    rest = body[match.end():]
    end = NEXT_SECTION_RE.search(rest)
    section = rest[: end.start()] if end else rest
    return [item for item in UNCHECKED_RE.findall(section)]


def evaluate(check_runs: list[dict], body: str) -> list[str]:
    """Return the blocking problems; empty means the machine-checkable gate is clean."""
    problems: list[str] = []
    coderabbit_seen = False

    for entry in check_runs or []:
        name = _name(entry)
        status = _status(entry)
        conclusion = _conclusion(entry)
        app = _app(entry)

        # A name match alone does not make a check a bot verdict: provenance
        # decides, so a forged job name is reported rather than trusted.
        name_says_coderabbit = "coderabbit" in name.lower()
        looks_like_coderabbit = name_says_coderabbit or app == CODERABBIT_APP
        if looks_like_coderabbit:
            coderabbit_seen = True

        if status in UNFINISHED:
            problems.append(f"check not finished: {name} (status={status})")
            continue
        if conclusion in FAILING:
            problems.append(f"check failed: {name} ({conclusion})")
            continue
        if looks_like_coderabbit:
            if app != CODERABBIT_APP:
                if app:
                    problems.append(
                        f"{name} check comes from app '{app}', not '{CODERABBIT_APP}'; "
                        "a matching name is not a bot verdict"
                    )
                else:
                    problems.append(
                        f"{name} check has no app provenance; request `@coderabbitai full review` "
                        "and read the resulting check run"
                    )
            elif conclusion in NOT_CLEAN:
                problems.append(
                    f"CodeRabbit is not clean on this head (conclusion={conclusion or 'none'}); "
                    "`skipping` means never requested"
                )

    if not coderabbit_seen:
        problems.append("no CodeRabbit check on this head; request `@coderabbitai full review`")

    boxes = bot_boxes(body)
    if boxes is None:
        problems.append(
            "PR body has no '## Bot review (gate)' section; the attestation boxes are required"
        )
    else:
        for box in boxes:
            problems.append(f"bot-review box unchecked: {box}")
    return problems


def fetch(pr: int, repo: str) -> tuple[list[dict], str]:
    """Read the head's check runs and the PR body through `gh`."""
    view = subprocess.run(
        ["gh", "pr", "view", str(pr), "--repo", repo, "--json", "headRefOid,body"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )
    if view.returncode != 0:
        raise RuntimeError((view.stderr or view.stdout).strip()[:400])
    meta = json.loads(view.stdout)

    sha = meta.get("headRefOid") or ""
    if not sha:
        raise RuntimeError("could not resolve the pull request head")

    runs = subprocess.run(
        ["gh", "api", f"repos/{repo}/commits/{sha}/check-runs"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )
    if runs.returncode != 0:
        raise RuntimeError((runs.stderr or runs.stdout).strip()[:400])
    return json.loads(runs.stdout).get("check_runs") or [], meta.get("body") or ""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("pr", type=int, help="pull request number")
    ap.add_argument("--repo", default="iap/pstack-hermes", help="owner/name (default: this project)")
    ap.add_argument("--json", dest="runs_file", default="", help="read check runs from a file")
    ap.add_argument("--body-file", default="", help="read the PR body from a file")
    args = ap.parse_args(argv)

    try:
        if args.runs_file and args.body_file:
            runs = json.loads(Path(args.runs_file).read_text(encoding="utf-8"))
            body = Path(args.body_file).read_text(encoding="utf-8")
        else:
            runs, body = fetch(args.pr, args.repo)
    except (OSError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"merge-gate: cannot read PR #{args.pr}: {exc}", file=sys.stderr)
        return 2

    problems = evaluate(runs, body)
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
