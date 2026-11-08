#!/usr/bin/env python3
"""Golden-task eval runner (#194).

Runs each tools/evals/golden/*.json prompt via `hermes -z` with the case's
skill preloaded (--skills), in an isolated HERMES_HOME seeded from the
active home's config.yaml/.env (provider access), with skills.external_dirs
pointing at this checkout's skills/, and cwd in an empty temp project so
live runs cannot modify the checkout. Rubric-scores the final response:
every must_mention must appear, no must_not_mention may appear, every gate
concept must appear. A non-zero hermes exit or timeout is a runner failure
(exit 2), never a rubric pass. Exit 0 = all pass; 1 = any rubric failure.

Scoring is unit-tested without hermes (tools/tests/test_evals.py).
Live runs are weekly/manual (cost + latency), never a per-PR gate.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
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


def seed_home(home: Path, active_home: Path | None) -> None:
    """Copy provider config into the isolated home; register checkout skills."""
    home.mkdir(parents=True, exist_ok=True)
    config = home / "config.yaml"
    if active_home is not None:
        for name in ("config.yaml", ".env"):
            src = active_home / name
            if src.is_file():
                shutil.copy2(src, home / name)
    try:
        import yaml
    except ImportError:
        return
    data = {}
    if config.is_file():
        data = yaml.safe_load(config.read_text(encoding="utf-8")) or {}
    skills = data.setdefault("skills", {})
    dirs = skills.setdefault("external_dirs", [])
    skills_dir = str(ROOT / "skills")
    if skills_dir not in dirs:
        dirs.append(skills_dir)
    config.write_text(yaml.safe_dump(data), encoding="utf-8")


def run_case(case: dict, hermes: str = "hermes") -> tuple[str, list[str]]:
    """Return ("pass"|"fail"|"error", failures)."""
    active = os.environ.get("HERMES_HOME")
    active_home = Path(active) if active else Path.home() / ".hermes"
    with tempfile.TemporaryDirectory(prefix="pstack-eval-") as td:
        home = Path(td) / "home"
        project = Path(td) / "project"
        project.mkdir(parents=True)
        seed_home(home, active_home if active_home.is_dir() else None)
        env = {**os.environ, "HERMES_HOME": str(home)}
        try:
            proc = subprocess.run(
                [hermes, "-z", case["prompt"], "--skills", case.get("skill", "")],
                capture_output=True,
                text=True,
                timeout=300,
                env=env,
                cwd=str(project),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return "error", [f"runner error: {exc}"]
    if proc.returncode != 0:
        tail = (proc.stdout + proc.stderr)[-500:]
        return "error", [f"hermes exited {proc.returncode}: {tail}"]
    ok, failures = score(case, proc.stdout)
    return ("pass" if ok else "fail"), failures


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--golden", default=str(GOLDEN_DIR))
    ap.add_argument("--hermes", default="hermes")
    args = ap.parse_args(argv)
    cases = load_golden(Path(args.golden))
    if not cases:
        print("evals: no golden tasks found", file=sys.stderr)
        return 2
    failed = errors = 0
    for case in cases:
        status, failures = run_case(case, args.hermes)
        print(f"{status.upper()} {case['id']}")
        for line in failures:
            print(f"  - {line}")
        failed += status == "fail"
        errors += status == "error"
    print(f"evals: {len(cases) - failed - errors}/{len(cases)} passed, {errors} runner errors")
    return 2 if errors else (1 if failed else 0)


if __name__ == "__main__":
    raise SystemExit(main())
