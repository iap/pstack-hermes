#!/usr/bin/env python3
"""Golden-task eval runner (#194).

Runs each tools/evals/golden/*.json prompt via `hermes -z` with the case's
skill preloaded (--skills), in an isolated HERMES_HOME seeded from the
active home's config.yaml/.env (provider access), with skills.external_dirs
pointing at a per-run snapshot of this checkout's skills/, and cwd in an
empty temp project so live runs cannot write to the checkout. Rubric-scores
the final response:
every must_mention must appear, no must_not_mention may appear, every gate
concept must appear. A non-zero hermes exit or timeout is a runner failure
(exit 2), never a rubric pass. Exit 0 = all pass; 1 = any rubric failure.

Arms (#212): `--arm skill` (default, unchanged) preloads the case skill and
registers a per-run snapshot of this checkout's skills; `--arm baseline` does neither, so the same
prompt runs without the method; `--arm both` runs each case in both arms and
prints the delta. `--reps N` repeats each case and reports pass counts, because
a single rep cannot separate a rubric failure from run-to-run variance.

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
import time
from datetime import UTC, datetime
from pathlib import Path

# Loaded both as a script (tools/evals on sys.path) and via importlib in tests.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from trajectory import grade as grade_trajectory
from trajectory import load_tool_calls

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_DIR = Path(__file__).resolve().parent / "golden"
ARMS = ("skill", "baseline")
CHECKOUT_SKILLS = str(ROOT / "skills")
SKILL_SNAPSHOT = "eval-skills"
PROJECT_TOKEN = "{PROJECT}"


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
        # `a|b` accepts any alternate: a rubric must not demand one phrasing.
        alternatives = [part.strip().lower() for part in term.split("|") if part.strip()]
        if not any(alt in lowered for alt in alternatives):
            failures.append(f"missing must_mention: {term}")
    for term in expect.get("must_not_mention", []):
        forbidden = [part.strip().lower() for part in term.split("|") if part.strip()]
        if any(alt in lowered for alt in forbidden):
            failures.append(f"forbidden present: {term}")
    for gate in expect.get("gates", []):
        if gate.lower() not in lowered:
            failures.append(f"missing gate concept: {gate}")
    return (not failures), failures


def build_argv(
    case: dict,
    hermes: str = "hermes",
    arm: str = "skill",
    model: str = "",
    project: Path | None = None,
) -> list[str]:
    """Command for one run. The baseline arm must not preload a skill.

    ``model`` pins the run to one provider model so a sweep is comparable; an
    empty value leaves the host's configured default in place. ``project``
    resolves the ``{PROJECT}`` token so prompts can name absolute fixture paths.
    """
    prompt = case["prompt"]
    if project is not None:
        prompt = prompt.replace(PROJECT_TOKEN, str(project))
    argv = [hermes, "-z", prompt]
    skill = case.get("skill", "")
    if arm == "skill" and skill:
        argv += ["--skills", skill]
    if model:
        argv += ["-m", model]
    return argv


def cleanup(path: Path, attempts: int = 3) -> bool:
    """Remove a run's temp tree, retrying while Hermes finishes flushing.

    Returns False when it still cannot be removed; the caller warns with the
    path instead of failing the sweep or silently leaking the directory.
    """
    for attempt in range(attempts):
        try:
            shutil.rmtree(path)
            return True
        except FileNotFoundError:
            return True
        except OSError:
            if attempt == attempts - 1:
                return False
            time.sleep(0.5 * (attempt + 1))
    return False


def preflight(hermes: str = "hermes", timeout: float = 60.0) -> tuple[bool, str]:
    """Fail in seconds when the CLI itself cannot start.

    A broken install (out-of-sync venv, update-paused gateway) otherwise burns
    the full per-case timeout before reporting an opaque error. Run against a
    throwaway HERMES_HOME: a version probe must not touch the live home or
    trigger its boot repairs.
    """
    with tempfile.TemporaryDirectory(prefix="pstack-preflight-") as home:
        env = {**os.environ, "HERMES_HOME": home, "HERMES_SUPERVISED_CHILD": "1"}
        try:
            proc = subprocess.run(
                [hermes, "--version"],
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return False, f"{hermes} --version failed: {exc}"
    if proc.returncode != 0:
        tail = (proc.stdout + proc.stderr).strip()[-300:]
        return False, f"{hermes} --version exited {proc.returncode}: {tail}"
    return True, (proc.stdout or proc.stderr).strip().splitlines()[0] if (proc.stdout or proc.stderr).strip() else "ok"


def probe_session_record(
    hermes: str = "hermes", timeout: float = 180.0, model: str = ""
) -> tuple[bool, str]:
    """Prove a one-shot run leaves a readable session record.

    ``--version`` passes on hosts where every turn is executed by a gateway
    that never persists a session; grading then reports "no readable session
    record" for every case. Probe before a sweep so such a host fails in
    seconds instead of hours.
    """
    with tempfile.TemporaryDirectory(prefix="pstack-probe-") as home_dir:
        home = Path(home_dir)
        active = os.environ.get("HERMES_HOME")
        active_home = Path(active) if active else Path.home() / ".hermes"
        try:
            seed_home(home, active_home if active_home.is_dir() else None, register_checkout_skills=False)
        except Exception as exc:
            return False, f"session probe seed failed: {exc}"
        env = build_env(home)
        argv = [hermes, "-z", "Reply with OK"]
        if model:
            argv += ["-m", model]
        try:
            proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, env=env)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return False, f"session probe failed: {exc}"
        if proc.returncode != 0:
            tail = (proc.stdout + proc.stderr).strip()[-300:]
            return False, f"session probe exited {proc.returncode}: {tail}"
        if load_tool_calls(home / "state.db") is None:
            return False, (
                "session probe left no readable session record; "
                "the gateway is not persisting one-shot turns for this HERMES_HOME"
            )
    return True, "one-shot session record readable"


def build_env(home: Path) -> dict[str, str]:
    """Environment for one eval run.

    ``HERMES_SUPERVISED_CHILD`` tells the launcher it was started by a manager,
    so boot does not try to finish a source update. On a dirty checkout that
    tail blocks every case for minutes before the model is even called — the
    harness must not inherit that repair obligation.
    """
    return {
        **os.environ,
        "HERMES_HOME": str(home),
        "HERMES_SUPERVISED_CHILD": "1",
    }


def seed_home(
    home: Path,
    active_home: Path | None,
    register_checkout_skills: bool = True,
) -> None:
    """Copy provider config into the isolated home; optionally register skills.

    The skill arm copies this checkout's skills into ``<home>/eval-skills`` and
    registers *that* path: a live run can edit the snapshot, never the package
    under test. Baseline arms register nothing and prune both the checkout path
    and any snapshot path from the copied config. Note this only removes *this
    checkout*; a skill installed in the active home's own config is inherited
    on purpose, so keep the eval host free of pstack installs when a clean
    baseline matters.
    """
    home.mkdir(parents=True, exist_ok=True)
    config = home / "config.yaml"
    if active_home is not None:
        # auth.json carries the provider credential the run needs; without it
        # the model call cannot authenticate and the case just times out.
        for name in ("config.yaml", ".env", "auth.json"):
            src = active_home / name
            if src.is_file():
                shutil.copy2(src, home / name)
                if name == "auth.json":
                    (home / name).chmod(0o600)
        # Reuse the installed runtime instead of letting the fresh home
        # provision one: PM install in a temp home is slow and, on this host,
        # ends in "source-update completion failed / update_paused".
        # Resolve before symlinking: a relative active_home would otherwise be
        # interpreted relative to the link's own directory.
        installs_src = (active_home / "installs").resolve()
        installs_dst = home / "installs"
        if installs_src.is_dir() and not installs_dst.exists():
            try:
                installs_dst.symlink_to(installs_src, target_is_directory=True)
            except OSError:
                # Windows without developer mode: run without the shortcut.
                pass
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("PyYAML is required to register eval skills") from exc
    data = {}
    if config.is_file():
        data = yaml.safe_load(config.read_text(encoding="utf-8")) or {}
    skills = data.setdefault("skills", {})
    dirs = skills.setdefault("external_dirs", [])
    snapshot = str(home / SKILL_SNAPSHOT)
    dirs = [d for d in dirs if d not in (CHECKOUT_SKILLS, snapshot)]
    if register_checkout_skills:
        target = home / SKILL_SNAPSHOT
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(
            ROOT / "skills",
            target,
            ignore=shutil.ignore_patterns("node_modules", "__pycache__", ".pytest_cache", ".DS_Store"),
        )
        dirs.append(snapshot)
    skills["external_dirs"] = dirs
    config.write_text(yaml.safe_dump(data), encoding="utf-8")


def seed_fixtures(project: Path, case: dict) -> None:
    """Write a case's fixtures into the temp project before the run."""
    root = project.resolve()
    for relative, content in case.get("fixtures", {}).items():
        target = (project / relative).resolve()
        if not target.is_relative_to(root):
            raise ValueError(f"fixture path escapes project: {relative}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def run_case(
    case: dict,
    hermes: str = "hermes",
    arm: str = "skill",
    model: str = "",
    timeout: float = 300,
) -> tuple[str, list[str], list[dict]]:
    """Return ("pass"|"fail"|"error", rubric failures, trajectory results)."""
    active = os.environ.get("HERMES_HOME")
    active_home = Path(active) if active else Path.home() / ".hermes"
    # Hermes may still be flushing state when the case returns; a cleanup race
    # must not abort the sweep (observed: OSError 66 'workspace').
    td = Path(tempfile.mkdtemp(prefix="pstack-eval-"))
    try:
        home = td / "home"
        project = td / "project"
        project.mkdir(parents=True)
        env = build_env(home)
        try:
            seed_fixtures(project, case)
            seed_home(
                home,
                active_home if active_home.is_dir() else None,
                register_checkout_skills=arm == "skill",
            )
        except Exception as exc:  # malformed YAML, non-mapping config, bad skills shape
            return "error", [f"seed error: {exc}"], []
        try:
            proc = subprocess.run(
                build_argv(case, hermes, arm, model, project),
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
                cwd=str(project),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return "error", [f"runner error: {exc}"], []

        # Grade before the temp home is removed. A missing record is an error,
        # never a pass: the gate could not see the evidence it claims to judge.
        process: list[dict] = []
        if case.get("process"):
            calls = load_tool_calls(home / "state.db")
            if calls is None:
                return "error", ["process: no readable session record"], []
            process = grade_trajectory(case["process"], calls, proc.stdout, project)

    finally:
        if not cleanup(td):
            print(f"evals: could not remove temp dir {td}", file=sys.stderr)

    if proc.returncode != 0:
        tail = (proc.stdout + proc.stderr)[-500:]
        return "error", [f"hermes exited {proc.returncode}: {tail}"], []
    ok, failures = score(case, proc.stdout)
    unavailable = [p for p in process if p["status"] == "unavailable"]
    if unavailable:
        return "error", [f"process {p['gate']}: {p['detail']}" for p in unavailable], process
    process_fail = [p for p in process if p["status"] == "fail"]
    for result in process_fail:
        failures.append(f"{result['gate']}: {result['detail']}")
    return ("pass" if ok and not process_fail else "fail"), failures, process


def summarize(records: list[dict], arms: tuple[str, ...]) -> list[dict]:
    """Aggregate per (case, arm) pass counts. ``records`` items: case, arm, status."""
    rows: dict[str, dict] = {}
    for record in records:
        row = rows.setdefault(record["case"], {arm: {"pass": 0, "total": 0, "error": 0} for arm in arms})
        cell = row[record["arm"]]
        cell["total"] += 1
        cell["pass"] += record["status"] == "pass"
        cell["error"] += record["status"] == "error"
    out = []
    for case_id, row in rows.items():
        out.append({"case": case_id, **row})
    return out


def _rate(cell: dict) -> float | None:
    """Pass rate over scored runs, or None when every run was a runner error.

    None is not 0%: an arm with no measurement must not produce a numeric delta.
    """
    scored = cell["total"] - cell["error"]
    return (cell["pass"] / scored * 100.0) if scored else None


def _print_summary(rows: list[dict], arms: tuple[str, ...], reps: int) -> None:
    header = f"{'case':34}" + "".join(f"{arm:>16}" for arm in arms)
    if arms == ARMS:
        header += f"{'delta':>10}"
    print(header)
    for row in rows:
        line = f"{row['case']:34}"
        for arm in arms:
            cell = row[arm]
            line += f"{cell['pass']}/{cell['total']}".rjust(16)
        if arms == ARMS:
            skill_rate, baseline_rate = _rate(row['skill']), _rate(row['baseline'])
            if skill_rate is None or baseline_rate is None:
                line += "n/a".rjust(10)
            else:
                line += f"{skill_rate - baseline_rate:+.0f}pp".rjust(10)
        print(line)
    print(f"evals: {reps} rep(s) per case")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--golden", default=str(GOLDEN_DIR))
    ap.add_argument("--hermes", default="hermes")
    ap.add_argument(
        "--arm",
        choices=("skill", "baseline", "both"),
        default="skill",
        help="skill: preload the case skill (default); baseline: no skill, no checkout skills; both: run each case in both arms",
    )
    ap.add_argument("--reps", type=int, default=1, help="runs per case (default 1)")
    ap.add_argument("--tasks", default="", help="comma-separated case ids (default: all)")
    ap.add_argument("--model", default="", help="pin every run to this provider model")
    ap.add_argument("--timeout", type=float, default=300, help="per-case seconds (default 300)")
    ap.add_argument(
        "--preflight-timeout", type=float, default=60, help="seconds for the --version probe (default 60)"
    )
    ap.add_argument(
        "--session-probe-timeout", type=float, default=180, help="seconds for the one-shot session probe (default 180)"
    )
    ap.add_argument("--json-out", default="", help="write the sweep (records + summary) to this path")
    args = ap.parse_args(argv)

    if args.reps < 1:
        print("evals: --reps must be >= 1", file=sys.stderr)
        return 2
    if args.timeout <= 0 or args.preflight_timeout <= 0 or args.session_probe_timeout <= 0:
        print("evals: --timeout, --preflight-timeout and --session-probe-timeout must be > 0", file=sys.stderr)
        return 2
    cases = load_golden(Path(args.golden))
    wanted = [task.strip() for task in args.tasks.split(",") if task.strip()]
    if wanted:
        cases = [case for case in cases if case.get("id") in wanted]
        missing = sorted(set(wanted) - {case.get("id") for case in cases})
        if missing:
            print(f"evals: unknown task id(s): {', '.join(missing)}", file=sys.stderr)
            return 2
    if not cases:
        print("evals: no golden tasks found", file=sys.stderr)
        return 2

    ok, detail = preflight(args.hermes, args.preflight_timeout)
    if not ok:
        print(f"evals: preflight failed — {detail}", file=sys.stderr)
        print("evals: repair the Hermes install first (`hermes update`, then restart the gateway)", file=sys.stderr)
        return 2
    print(f"evals: {detail}")

    probe_ok, probe_detail = probe_session_record(args.hermes, args.session_probe_timeout, args.model)
    if not probe_ok:
        print(f"evals: session probe failed — {probe_detail}", file=sys.stderr)
        print("evals: use a host where `hermes -z` persists a session record (see docs/EVALS.md)", file=sys.stderr)
        return 2
    print(f"evals: {probe_detail}")

    arms = ARMS if args.arm == "both" else (args.arm,)
    records: list[dict] = []
    errors = 0
    skill_errors = 0
    skill_failed = 0

    for case in cases:
        for arm in arms:
            for rep in range(1, args.reps + 1):
                status, failures, process = run_case(
                    case, args.hermes, arm, args.model, args.timeout
                )
                suffix = f" rep{rep}" if args.reps > 1 else ""
                print(f"{status.upper()} {case['id']} [{arm}]{suffix}")
                for line in failures:
                    print(f"  - {line}")
                for result in process:
                    print(f"  process {result['gate']}: {result['status']} ({result['detail']})")
                records.append(
                    {
                        "case": case["id"],
                        "arm": arm,
                        "rep": rep,
                        "status": status,
                        "failures": failures,
                        "process": process,
                    }
                )
                errors += status == "error"
                # Baseline runner errors are data (the delta becomes n/a), not a
                # gate failure. Only the skill arm measures the method.
                skill_errors += status == "error" and arm == "skill"
                skill_failed += status == "fail" and arm == "skill"

    summary = summarize(records, arms)
    _print_summary(summary, arms, args.reps)
    print(f"evals: {errors} runner error(s), {skill_failed} skill-arm rubric failure(s)")

    if args.json_out:
        payload = {
            "schema_version": "1",
            "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "hermes": detail,
            "model": args.model,
            "arms": list(arms),
            "reps": args.reps,
            "records": records,
            "summary": summary,
        }
        target = Path(args.json_out)
        temp = target.with_name(target.name + ".tmp")
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            # Write beside the target and replace atomically: a failed write
            # must not truncate a sweep recorded earlier.
            temp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            os.replace(temp, target)
        except OSError as exc:
            try:
                temp.unlink(missing_ok=True)
            except OSError:
                pass  # the parent path may itself be unusable; nothing to clean
            print(f"evals: could not write {target}: {exc}", file=sys.stderr)
            return 2
        print(f"evals: wrote {target}")

    baseline_only = arms == ("baseline",)
    if skill_errors or (baseline_only and errors):
        return 2
    return 1 if skill_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
