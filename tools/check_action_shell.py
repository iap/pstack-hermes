#!/usr/bin/env python3
"""Shellcheck every composite action's `run:` blocks.

`actionlint` covers workflow files, but it does not lint the steps inside
`.github/actions/*/action.yml` - verified against 1.7.12: a deliberately
injected shell error in a referenced composite action goes unreported. The
shared bash lives in those actions, so a bug there - like the subshell-captured
exit status that made the drift watchers' duplicate-guard unfirable - would
otherwise ship with no static check.

This extracts each `run:` block with PyYAML and pipes it to the same shellcheck
binary actionlint uses (dev dependency `shellcheck-py`), so both gates agree on
what "clean" means. Exit codes: 0 clean, 1 findings, 2 input/shellcheck missing.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
ACTIONS_DIR = ROOT / ".github" / "actions"

# shellcheck needs a filename to report against; .sh keeps it in bash mode with
# the -s flag below regardless of extension, but the name makes output readable.
TMP_NAME = "action-step.sh"


def run_blocks(action_file: Path) -> list[tuple[int, str]]:
    """Return (step_index, script) for every run: step in a composite action."""
    data = yaml.safe_load(action_file.read_text(encoding="utf-8"))
    runs = (data or {}).get("runs") or {}
    if runs.get("using") != "composite":
        return []
    blocks: list[tuple[int, str]] = []
    for i, step in enumerate(runs.get("steps") or []):
        script = step.get("run")
        if isinstance(script, str) and script.strip():
            blocks.append((i, script))
    return blocks


def shellcheck_binary() -> str | None:
    return shutil.which("shellcheck")


def check(root: Path = ROOT) -> tuple[int, list[str]]:
    """Run the check; return (exit_code, report lines)."""
    actions_dir = root / ".github" / "actions"
    if not actions_dir.is_dir():
        return 2, [f"error: no actions directory at {actions_dir}"]
    files = sorted(p for p in actions_dir.glob("*/action.y*ml"))
    if not files:
        return 2, [f"error: no composite actions found under {actions_dir}"]

    report: list[str] = []
    failed = False

    # Collect first, resolve shellcheck second: a tree whose actions have no
    # composite run steps needs no shellcheck at all, and demanding one there
    # would turn a clean no-op into a tool error.
    pending: list[tuple[str, int, str]] = []
    for action_file in files:
        rel = action_file.relative_to(root).as_posix()
        blocks = run_blocks(action_file)
        if not blocks:
            report.append(f"skip: {rel} (no composite run steps)")
            continue
        pending.extend((rel, idx, script) for idx, script in blocks)

    if not pending:
        return 0, report

    sc = shellcheck_binary()
    if sc is None:
        return 2, [
            "error: shellcheck not found on PATH.",
            "Run this via `uv run --frozen python tools/check_action_shell.py`,",
            "or `uv sync` first - shellcheck-py is a dev dependency.",
        ]

    for rel, idx, script in pending:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td) / TMP_NAME
            tmp.write_text(script, encoding="utf-8", newline="\n")
            proc = subprocess.run(
                [sc, "-s", "bash", str(tmp)],
                capture_output=True,
                text=True,
                check=False,
            )
        if proc.returncode == 0:
            continue
        failed = True
        report.append(f"FAIL: {rel} step[{idx}]")
        for line in (proc.stdout or "").splitlines():
            # Rewrite the temp path back to the real file for readable output.
            report.append("  " + line.replace(str(tmp), rel))
    return (1 if failed else 0), report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="check_action_shell.py", description=__doc__)
    ap.add_argument("--root", type=Path, default=ROOT, help="repository root")
    args = ap.parse_args(argv)
    code, report = check(args.root)
    stream = sys.stderr if code else sys.stdout
    for line in report:
        print(line, file=stream)
    if code == 0:
        print("composite action shell blocks: clean")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
