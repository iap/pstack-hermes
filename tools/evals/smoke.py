#!/usr/bin/env python3
"""Deterministic-first smoke checks for the eval tooling (issue #260).

Default runs only deterministic checks. Live model-calling checks require
``--live --model <slug>`` and are reported but never promoted to a CI gate.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import run  # noqa: E402
import trajectory  # noqa: E402
import yaml  # noqa: E402

DETERMINISTIC = (
    ("validate", "deterministic"),
    ("check_docs", "deterministic"),
    ("scanner_vocab", "deterministic"),
    ("dual_lock", "deterministic"),
    ("plugin_doctor", "deterministic"),
    ("seed_home_baseline", "deterministic"),
    ("trajectory_negative", "deterministic"),
)
LIVE = (("activation", "live"), ("delegate", "live"))


def select_checks(live: bool, model: str | None) -> list[tuple[str, str]]:
    checks = list(DETERMINISTIC)
    if live:
        if not model:
            raise ValueError("model is required for live checks")
        checks.extend(LIVE)
    return checks


def make_record(checks: list[dict], host: dict, model: str | None = None) -> dict:
    return {
        "schema_version": "1",
        "generated_at": datetime.now(UTC).isoformat(),
        "host": host,
        "model": model,
        "checks": checks,
        "summary": {
            "pass": sum(c["status"] == "pass" for c in checks),
            "fail": sum(c["status"] == "fail" for c in checks),
        },
    }


def result(name: str, tier: str, status: str, detail: str) -> dict:
    return {"name": name, "tier": tier, "status": status, "detail": detail}


def command_check(name: str, tier: str, argv: list[str], cwd: Path, timeout: int = 300) -> dict:
    try:
        proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return result(name, tier, "fail", f"could not run {argv[0]}: {exc}")
    detail = (proc.stdout + proc.stderr).strip().splitlines()
    tail = detail[-1] if detail else "no output"
    status = "pass" if proc.returncode == 0 else "fail"
    return result(name, tier, status, f"rc={proc.returncode} {tail[:300]}")


def check_seed_home(root: Path, active: Path) -> dict:
    name, tier = "seed_home_baseline", "deterministic"
    try:
        with tempfile.TemporaryDirectory(prefix="pstack-smoke-home-") as tmp:
            home = Path(tmp)
            run.seed_home(home, active, register_checkout_skills=False)
            config = home / "config.yaml"
            data = yaml.safe_load(config.read_text(encoding="utf-8")) if config.is_file() else {}
            dirs = (data.get("skills") or {}).get("external_dirs") or []
            snapshot = str(home / run.SKILL_SNAPSHOT)
            if str(run.CHECKOUT_SKILLS) in dirs or snapshot in dirs or (home / run.SKILL_SNAPSHOT).exists():
                return result(name, tier, "fail", "baseline registered checkout skills")
    except Exception as exc:  # a smoke failure must be visible, not silent
        return result(name, tier, "fail", f"seed_home: {exc}")
    return result(name, tier, "pass", "no checkout skills in baseline")


def check_trajectory_negative() -> dict:
    name, tier = "trajectory_negative", "deterministic"
    strict = [{"name": "terminal", "args": {"command": "pytest -q"}, "exit_code": 0}]
    masked = [{"name": "terminal", "args": {"command": "pytest -q | tee out"}, "exit_code": 0}]
    delegate = [{"name": "delegate_task", "args": {"tasks": [{"goal": "x"}]}, "exit_code": 0}]
    nested = [
        {"name": "delegate_task", "args": {"tasks": [{"goal": "x", "subagent_type": "general"}]}, "exit_code": 0}
    ]
    deep = [
        {"name": "delegate_task", "args": {"tasks": [{"meta": {"generalPurpose": True}}]}, "exit_code": 0}
    ]
    banned = [{"name": "delegate_task", "args": {"subagent_type": "general"}, "exit_code": 0}]
    with tempfile.TemporaryDirectory(prefix="pstack-smoke-proj-") as tmp:
        project = Path(tmp)
        def grade(calls, final, gates):
            return trajectory.grade({"gates": gates}, calls, final, project)
        cases = [
            ("strict pytest passes", grade(strict, "All tests pass.", ["verification_present"])[0]["status"] == "pass"),
            ("piped pytest unavailable", grade(masked, "All tests pass.", ["verification_present"])[0]["status"] == "unavailable"),
            ("missing record unavailable", grade(None, "All tests pass.", ["verification_present"])[0]["status"] == "unavailable"),
            ("bare claim fails", grade([], "All tests pass.", ["verify_before_claim"])[0]["status"] == "fail"),
            ("delegate accepted", grade(delegate, "", ["no_banned_tool"])[0]["status"] == "pass"),
            ("nested banned key fails", grade(nested, "", ["no_banned_tool"])[0]["status"] == "fail"),
            ("deep banned key fails", grade(deep, "", ["no_banned_tool"])[0]["status"] == "fail"),
            ("top-level banned key fails", grade(banned, "", ["no_banned_tool"])[0]["status"] == "fail"),
        ]
    failures = [label for label, good in cases if not good]
    if failures:
        return result(name, tier, "fail", "false verdicts: " + ", ".join(failures))
    return result(name, tier, "pass", f"{len(cases)} negative cases default-deny")


def live_activation(root: Path, hermes: str, model: str) -> dict:
    name, tier = "activation", "live"
    skill = root / "skills" / "poteto-mode" / "SKILL.md"
    quote = "The Principles section below grounds every trigger."
    if skill.is_file() and quote not in skill.read_text(encoding="utf-8"):
        return result(name, tier, "fail", "quote missing from shipped skill")
    prompt = "Quote verbatim the first Non-negotiables sentence from poteto-mode. Answer with only that sentence."
    try:
        proc = subprocess.run(
            [hermes, "-z", prompt, "-m", model], capture_output=True, text=True, timeout=420
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return result(name, tier, "fail", f"one-shot failed: {exc}")
    status = "pass" if proc.returncode == 0 and quote in (proc.stdout + proc.stderr) else "fail"
    return result(name, tier, status, f"rc={proc.returncode} verbatim_quote={quote in proc.stdout}")


def live_delegate(active: Path, hermes: str, model: str) -> dict:
    name, tier = "delegate", "live"
    prompt = "Use delegate_task exactly once with a trivial read-only goal: ask the child to reply with OK. Then report the child reply in one line."
    try:
        proc = subprocess.run(
            [hermes, "-z", prompt, "-m", model], capture_output=True, text=True, timeout=500
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return result(name, tier, "fail", f"delegate one-shot failed: {exc}")
    db = active / "state.db"
    child_model = "unknown"
    if db.is_file():
        try:
            conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            row = conn.execute(
                "SELECT model FROM sessions WHERE source='subagent' ORDER BY started_at DESC LIMIT 1"
            ).fetchone()
            child_model = row[0] if row else "unknown"
            conn.close()
        except sqlite3.Error as exc:
            return result(name, tier, "fail", f"session record unreadable: {exc}")
    status = "pass" if proc.returncode == 0 and child_model != "unknown" else "fail"
    return result(name, tier, status, f"rc={proc.returncode} child_model={child_model}")


def host_metadata(root: Path, hermes: str) -> dict:
    version = "unknown"
    try:
        proc = subprocess.run([hermes, "--version"], capture_output=True, text=True, timeout=60)
        version = (proc.stdout or proc.stderr).strip().splitlines()[0]
    except (OSError, subprocess.TimeoutExpired):
        pass
    return {
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "hermes": version,
        "root": str(root),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--live", action="store_true", help="include live model-calling checks")
    ap.add_argument("--model", help="model slug; required with --live")
    ap.add_argument("--hermes", default=shutil.which("hermes") or "hermes")
    ap.add_argument("--active-home", type=Path, default=None)
    ap.add_argument("--json-out", type=Path, default=None)
    args = ap.parse_args(argv)

    checks = select_checks(args.live, args.model)
    active = (args.active_home or Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))).resolve()
    results: list[dict] = []
    for name, tier in checks:
        if name == "validate":
            entry = command_check(name, tier, [sys.executable, str(args.root / "tools/validate.py")], args.root)
        elif name == "check_docs":
            entry = command_check(name, tier, [sys.executable, str(args.root / "tools/check_docs.py")], args.root)
        elif name == "scanner_vocab":
            entry = command_check(name, tier, [sys.executable, str(args.root / "tools/scanner_gate.py"), "--package", str(args.root), "--vocab-only"], args.root)
        elif name == "dual_lock":
            entry = command_check(name, tier, [sys.executable, str(args.root / "tools/check_dual_lock.py")], args.root)
        elif name == "plugin_doctor":
            entry = command_check(name, tier, [args.hermes, "plugins", "doctor", str(args.root), "--ci"], args.root, timeout=180)
        elif name == "seed_home_baseline":
            entry = check_seed_home(args.root, active)
        elif name == "trajectory_negative":
            entry = check_trajectory_negative()
        elif name == "activation":
            entry = live_activation(args.root, args.hermes, args.model)
        elif name == "delegate":
            entry = live_delegate(active, args.hermes, args.model)
        else:
            entry = result(name, tier, "fail", "unknown check")
        results.append(entry)
        print(f"[{entry['status'].upper():4}] {name} ({tier}) {entry['detail']}")

    record = make_record(results, host_metadata(args.root, args.hermes), args.model if args.live else None)
    if args.json_out:
        args.json_out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        print(f"record: {args.json_out}")
    print(f"summary: pass={record['summary']['pass']} fail={record['summary']['fail']}")
    return 1 if record["summary"]["fail"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
