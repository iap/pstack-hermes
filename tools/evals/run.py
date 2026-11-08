#!/usr/bin/env python3
"""Golden-task eval runner (#194).

Runs each tools/evals/golden/*.json prompt via `hermes -z` in an isolated
HERMES_HOME, then rubric-scores the response: every must_mention must
appear, no must_not_mention may appear, every gate concept must appear.
Exit 0 = all golden tasks pass; 1 = any failure; 2 = runner error.

Scoring is unit-tested without hermes (tools/tests/test_evals.py).
Live runs are weekly/manual (cost + latency), never a per-PR gate.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_DIR = Path(__file__).resolve().parent / "golden"


def load_golden(directory: Path = GOLDEN_DIR) -> list[dict]:
    cases = []
    for path in sorted(directory.glob("*.json")):
        cases.append(json.loads(path.read_text(encoding="utf-8")))
    return cases


def score(case: dict, response: str) -> tuple[bool, list[str]]:
    expect = case.get("expect", {})
    failures: list[str] = []
    lowered = response.lower()
    for term in expect.get("must_mention", []):
        if term.lower() not in lowered:
            failures.append(f"missing must_mention: {term}")
    for term in expect.get("must_not_mention", []):
        if term.lower() in lowered:
            failures.append(f"forbidden present: {term}")
    for gate in expect.get("gates", []):
        if gate.lower() not in lowered:
            failures.append(f"missing gate concept: {gate}")
    return (not failures), failures


def run_case(case: dict, hermes: str = "hermes") -> tuple[bool, list[str]]:
    with tempfile.TemporaryDirectory(prefix="pstack-eval-") as home:
        env = {**os.environ, "HERMES_HOME": home}
        try:
            proc = subprocess.run(
                [hermes, "-z", case["prompt"]],
                capture_output=True,
                text=True,
                timeout=300,
                env=env,
                cwd=str(ROOT),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return False, [f"runner error: {exc}"]
    return score(case, proc.stdout + proc.stderr)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--golden", default=str(GOLDEN_DIR))
    ap.add_argument("--hermes", default="hermes")
    args = ap.parse_args(argv)
    cases = load_golden(Path(args.golden))
    if not cases:
        print("evals: no golden tasks found", file=sys.stderr)
        return 2
    failed = 0
    for case in cases:
        ok, failures = run_case(case, args.hermes)
        status = "PASS" if ok else "FAIL"
        print(f"{status} {case['id']}")
        for line in failures:
            print(f"  - {line}")
        failed += 0 if ok else 1
    print(f"evals: {len(cases) - failed}/{len(cases)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
