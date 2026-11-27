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
import sqlite3
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

# Loaded both as a script (tools/evals on sys.path) and via importlib in tests.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from trajectory import grade as grade_trajectory
from trajectory import load_all_tool_calls, load_tool_calls

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_DIR = Path(__file__).resolve().parent / "golden"
ARMS = ("skill", "baseline")
OFFLINE_ARM = "offline"
ALL_ARMS = ARMS + (OFFLINE_ARM,)
RESTRICTED_TOOLSETS = "file,todo,clarify"
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
    if arm == OFFLINE_ARM:
        argv += ["-t", RESTRICTED_TOOLSETS]
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


def session_has_turns(db_path: Path) -> bool:
    """True only when the record holds both a user turn and an assistant turn."""
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.Error:
        return False
    try:
        roles = {row[0] for row in conn.execute("SELECT DISTINCT role FROM messages")}
    except sqlite3.Error:
        return False
    finally:
        conn.close()
    return "user" in roles and "assistant" in roles


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
        db = home / "state.db"
        for _ in range(5):
            if session_has_turns(db) and load_tool_calls(db) is not None:
                break
            time.sleep(0.1)
        else:
            return False, (
                "session probe left no readable user and assistant turn; "
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
    skills_root: Path | None = None,
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
    checkout_skills = str((skills_root or ROOT) / "skills")
    dirs = [d for d in dirs if d not in (checkout_skills, snapshot)]
    if register_checkout_skills:
        target = home / SKILL_SNAPSHOT
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(
            (skills_root or ROOT) / "skills",
            target,
            ignore=shutil.ignore_patterns("node_modules", "__pycache__", ".pytest_cache", ".DS_Store"),
        )
        scripts_dst = home / "scripts"
        if scripts_dst.exists():
            shutil.rmtree(scripts_dst)
        shutil.copytree(
            (skills_root or ROOT) / "scripts",
            scripts_dst,
            ignore=shutil.ignore_patterns("node_modules", "__pycache__", ".pytest_cache", ".DS_Store"),
        )
        dirs.append(snapshot)
    skills["external_dirs"] = dirs
    config.write_text(yaml.safe_dump(data), encoding="utf-8")


def _project_path(project: Path, relative: str) -> Path:
    target = (project / relative).resolve()
    if not target.is_relative_to(project.resolve()):
        raise ValueError(f"path escapes project: {relative}")
    return target


def seed_fixtures(project: Path, case: dict) -> None:
    """Write a case's fixtures into the temp project before the run."""
    for relative, content in case.get("fixtures", {}).items():
        target = _project_path(project, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def check_outcomes(case: dict, project: Path) -> list[str]:
    """Assert the run changed and completed the fixture work, not just talked."""
    expect = case.get("expect", {})
    failures: list[str] = []
    for relative in expect.get("files_changed", []):
        target = _project_path(project, relative)
        original = case.get("fixtures", {}).get(relative)
        if original is None:
            failures.append(f"files_changed: no fixture baseline for {relative}")
        elif not target.is_file():
            failures.append(f"files_changed: missing {relative}")
        elif target.read_text(encoding="utf-8") == original:
            failures.append(f"files_changed: {relative} unchanged")
    for item in expect.get("file_contains", []):
        target = _project_path(project, item["path"])
        if not target.is_file():
            failures.append(f"file_contains: missing {item['path']}")
        elif item["text"].lower() not in target.read_text(encoding="utf-8").lower():
            failures.append(f"file_contains: {item['path']} lacks {item['text']}")
    return failures


def run_protected_tests(case: dict, project: Path, protected: Path) -> list[str]:
    """Run original tests against the agent's result from an agent-unwritable tree."""
    names = case.get("verify_tests", [])
    if not names:
        return []
    fixtures = case.get("fixtures", {})
    changed = set(case.get("expect", {}).get("files_changed", []))
    protected.mkdir(parents=True, exist_ok=True)
    for name, original in fixtures.items():
        target = _project_path(protected, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        if name in changed and name not in names:
            source = _project_path(project, name)
            if not source.is_file():
                return [f"protected test: missing result {name}"]
            target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            target.write_text(original, encoding="utf-8")
    for name in names:
        if name not in fixtures:
            return [f"protected test: no fixture for {name}"]
    env = {**os.environ, "PYTHONPATH": str(protected)}
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *names],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(protected),
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return [f"protected test: {exc}"]
    if proc.returncode != 0:
        return [f"protected test failed: {(proc.stdout + proc.stderr)[-500:]}"]
    return []


def run_case(
    case: dict,
    hermes: str = "hermes",
    arm: str = "skill",
    model: str = "",
    timeout: float = 1200,
) -> tuple[str, list[str], list[dict]]:
    """Return ("pass"|"fail"|"error", rubric failures, trajectory results)."""
    if arm == OFFLINE_ARM:
        process = case.get("process", {})
        gates = list(dict.fromkeys([*process.get("gates", []), "no_unverified_claim"]))
        case = {**case, "process": {**process, "gates": gates}}
    active = os.environ.get("HERMES_HOME")
    active_home = Path(active) if active else Path.home() / ".hermes"
    # Hermes may still be flushing state when the case returns; a cleanup race
    # must not abort the sweep (observed: OSError 66 'workspace').
    td = Path(tempfile.mkdtemp(prefix="pstack-eval-"))
    outcome_failures: list[str] = []
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
            all_calls = load_all_tool_calls(home / "state.db")
            if all_calls is None and any(
                gate in ("verification_present", "verify_before_claim", "no_unverified_claim")
                for gate in case["process"]["gates"]
            ):
                return "error", ["process: no readable all-session record"], []
            process = grade_trajectory(
                case["process"], calls, proc.stdout, project, all_calls,
                delegation_available=arm != OFFLINE_ARM,
            )
        try:
            outcome_failures = check_outcomes(case, project)
            outcome_failures += run_protected_tests(case, project, td / "protected")
        except Exception as exc:
            return "error", [f"outcome check error: {exc}"], []

    finally:
        if not cleanup(td):
            print(f"evals: could not remove temp dir {td}", file=sys.stderr)

    if proc.returncode != 0:
        tail = (proc.stdout + proc.stderr)[-500:]
        return "error", [f"hermes exited {proc.returncode}: {tail}"], []
    ok, failures = score(case, proc.stdout)
    failures = outcome_failures + failures
    unavailable = [p for p in process if p["status"] == "unavailable"]
    if unavailable:
        return "error", [f"process {p['gate']}: {p['detail']}" for p in unavailable], process
    process_fail = [p for p in process if p["status"] == "fail"]
    for result in process_fail:
        failures.append(f"{result['gate']}: {result['detail']}")
    return ("pass" if ok and not process_fail and not outcome_failures else "fail"), failures, process


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
    comparable = "skill" in arms and "baseline" in arms
    if comparable:
        header += f"{'delta':>10}"
    print(header)
    for row in rows:
        line = f"{row['case']:34}"
        for arm in arms:
            cell = row[arm]
            line += f"{cell['pass']}/{cell['total']}".rjust(16)
        if comparable:
            skill_rate, baseline_rate = _rate(row['skill']), _rate(row['baseline'])
            if skill_rate is None or baseline_rate is None:
                line += "n/a".rjust(10)
            else:
                line += f"{skill_rate - baseline_rate:+.0f}pp".rjust(10)
        print(line)
    print(f"evals: {reps} rep(s) per case")


def write_sweep(payload: dict, target: Path) -> None:
    """Replace the record atomically so an interrupted sweep keeps its last write."""
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(target.name + ".tmp")
    try:
        temp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        os.replace(temp, target)
    except OSError:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--golden", default=str(GOLDEN_DIR))
    ap.add_argument("--hermes", default="hermes")
    ap.add_argument(
        "--arm",
        choices=("skill", "baseline", "both", OFFLINE_ARM, "all"),
        default="skill",
        help="skill: preload the case skill (default); baseline: no skill, no checkout skills; both: skill+baseline delta; offline: restricted tools; all: every arm",
    )
    ap.add_argument("--reps", type=int, default=1, help="runs per case (default 1)")
    ap.add_argument("--tasks", default="", help="comma-separated case ids (default: all)")
    ap.add_argument("--model", default="", help="pin every run to this provider model")
    ap.add_argument("--timeout", type=float, default=1200, help="per-case seconds (default 1200)")
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

    arms = ARMS if args.arm == "both" else ALL_ARMS if args.arm == "all" else (args.arm,)
    records: list[dict] = []
    errors = 0
    skill_errors = 0
    skill_failed = 0
    offline_errors = 0
    offline_failed = 0
    target = Path(args.json_out) if args.json_out else None
    payload = None
    if target is not None:
        payload = {
            "schema_version": "1",
            "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "hermes": detail,
            "model": args.model,
            "arms": list(arms),
            "reps": args.reps,
            "records": records,
            "summary": summarize(records, arms),
        }
        try:
            write_sweep(payload, target)
        except OSError as exc:
            print(f"evals: could not write {target}: {exc}", file=sys.stderr)
            return 2

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
                offline_errors += status == "error" and arm == OFFLINE_ARM
                offline_failed += status == "fail" and arm == OFFLINE_ARM
                if payload is not None:
                    payload["summary"] = summarize(records, arms)
                    try:
                        write_sweep(payload, target)
                    except OSError as exc:
                        print(f"evals: could not write {target}: {exc}", file=sys.stderr)
                        return 2

    summary = summarize(records, arms)
    _print_summary(summary, arms, args.reps)
    print(
        f"evals: {errors} runner error(s), {skill_failed} skill-arm rubric failure(s), "
        f"{offline_failed} offline-arm rubric failure(s)"
    )

    if payload is not None:
        payload["summary"] = summary
        try:
            write_sweep(payload, target)
        except OSError as exc:
            print(f"evals: could not write {target}: {exc}", file=sys.stderr)
            return 2
        print(f"evals: wrote {target}")

    baseline_only = arms == ("baseline",)
    if skill_errors or offline_errors or (baseline_only and errors):
        return 2
    return 1 if skill_failed or offline_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
