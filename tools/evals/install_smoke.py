#!/usr/bin/env python3
"""Installed-user lifecycle test (evals tier 4).

Installs the published package into a throwaway ``HERMES_HOME`` and walks the
whole user lifecycle — install, doctor, remove, reinstall pinned to a commit,
update — asserting the tree at every stop.

This is the only gate that covers the failure class behind #168 (root
``scripts/`` missing from the installed skill view) and #169 (a generated npm
lockfile breaking ``hermes plugins update``). The static gates in ``tools/``
cannot see either: they never install anything.

Usage::

    python tools/evals/install_smoke.py
    python tools/evals/install_smoke.py --ref 08db89f384c8fbf63ece78e6ec8d116dfd7b0aec
    python tools/evals/install_smoke.py --no-lifecycle      # install + doctor only
    python tools/evals/install_smoke.py --validate tools/validate.py --keep

Needs the ``hermes`` CLI on PATH and network access for the clone. No provider
credentials: nothing here runs a model turn.

Exit codes: 0 all steps passed; 1 a step failed; 2 the runner could not start
(no hermes CLI, unusable temp home).
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
PLUGIN_NAME = "pstack"


class StepFailed(Exception):
    """A smoke-test step failed; the message is the user-facing reason."""


def run(
    cmd: list[str], *, env: dict[str, str], timeout: int = 600, allow_fail: bool = False
) -> tuple[int, str]:
    """Run a command. Returns (returncode, combined output).

    A non-zero exit raises StepFailed unless *allow_fail*; callers that tolerate
    failure inspect the code and output themselves.
    """
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
            cwd=str(ROOT),
        )
    except FileNotFoundError as exc:
        raise StepFailed(f"cannot run {cmd[0]!r}: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise StepFailed(f"{' '.join(cmd)} timed out after {timeout}s") from exc
    out = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0 and not allow_fail:
        tail = out.strip().splitlines()[-12:]
        raise StepFailed(f"{' '.join(cmd)} exited {proc.returncode}:\n  " + "\n  ".join(tail))
    return proc.returncode, out


def find_installed(home: Path) -> Path:
    """Locate the installed plugin directory, or raise."""
    candidate = home / "plugins" / PLUGIN_NAME
    if (candidate / "plugin.json").is_file():
        return candidate
    for manifest in home.rglob("plugin.json"):
        if manifest.parent.name == PLUGIN_NAME:
            return manifest.parent
    raise StepFailed(f"no installed package found under {home}")


def count_skills(root: Path) -> int:
    return sum(1 for _ in root.glob("skills/*/SKILL.md"))


def assert_absent(home: Path) -> None:
    """The plugin directory and its manifest must be gone after a remove."""
    stale = home / "plugins" / PLUGIN_NAME
    if stale.exists():
        raise StepFailed(f"remove left the install directory behind: {stale}")
    for manifest in home.rglob("plugin.json"):
        if manifest.parent.name == PLUGIN_NAME:
            raise StepFailed(f"remove left a manifest behind: {manifest}")


def listing_contains(entries: object, name: str) -> bool:
    """Tolerant membership test over ``hermes plugins list --json`` output.

    The JSON shape is hermes' business, not ours: accept a list of objects, a
    dict of objects, or any nesting where the plugin name appears as a value.
    """
    if isinstance(entries, dict):
        entries = list(entries.values())
    if not isinstance(entries, list):
        return False
    for entry in entries:
        if isinstance(entry, str) and entry == name:
            return True
        if isinstance(entry, dict):
            if any(value == name for value in entry.values()):
                return True
    return False


def listed(hermes: str, env: dict[str, str]) -> bool:
    _, out = run([hermes, "plugins", "list", "--json", "--user"], env=env, allow_fail=True)
    start = out.find("[")
    start = 0 if start < 0 else start
    try:
        parsed = json.loads(out[start:])
    except json.JSONDecodeError:
        return PLUGIN_NAME in out
    return listing_contains(parsed, PLUGIN_NAME)


def assert_tree(installed: Path, expected_skills: int | None) -> dict[str, str]:
    """Structural assertions on the installed tree. Returns facts for the report."""
    facts: dict[str, str] = {}
    if not (installed / "plugin.json").is_file():
        raise StepFailed("installed tree has no plugin.json")

    skills = count_skills(installed)
    if skills == 0:
        raise StepFailed("installed tree ships no skills/*/SKILL.md")
    if expected_skills is not None and skills != expected_skills:
        raise StepFailed(f"installed {skills} skills, source tree has {expected_skills}")
    facts["skills"] = str(skills)

    # #168: the orchestrator's root tooling must survive packaging.
    for rel in ("scripts/orch", "scripts/watch-pr"):
        if not (installed / rel).exists():
            raise StepFailed(f"installed tree is missing {rel} (regression class #168)")
    facts["scripts"] = "orch + watch-pr present"

    # #169: the dual lockfile is what hermes' npm ci sidecar needs.
    for rel in ("package.json", "bun.lock", "package-lock.json"):
        if not (installed / rel).is_file():
            raise StepFailed(f"installed tree is missing {rel} (regression class #169)")
    facts["lockfiles"] = "package.json + bun.lock + package-lock.json"

    if not (installed / "config" / "models.json").is_file():
        raise StepFailed("installed tree is missing config/models.json")
    facts["model_panel"] = "config/models.json present"
    return facts


def installed_commit(installed: Path) -> str:
    """Commit the installed clone sits on, or "" when it is not a git checkout."""
    try:
        out = subprocess.run(
            ["git", "-C", str(installed), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return (out.stdout or "").strip() if out.returncode == 0 else ""


def install(hermes: str, env: dict[str, str], identifier: str, ref: str) -> None:
    cmd = [hermes, "plugins", "install", identifier, "--enable", "--yes-deps"]
    if ref:
        cmd += ["--ref", ref]
    run(cmd, env=env)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--hermes", default="hermes", help="hermes executable (default: hermes)")
    ap.add_argument(
        "--identifier", default="iap/pstack-hermes", help="install target: owner/repo or Git URL"
    )
    ap.add_argument("--ref", default="", help="pin every install to one 40-character commit SHA")
    ap.add_argument(
        "--validate", default="", help="path to tools/validate.py to run against the installed tree"
    )
    ap.add_argument(
        "--no-lifecycle", action="store_true", help="stop after install + doctor + assertions"
    )
    ap.add_argument("--keep", action="store_true", help="keep the temp HERMES_HOME for inspection")
    args = ap.parse_args(argv)

    hermes = shutil.which(args.hermes)
    if hermes is None:
        print(f"install-smoke: cannot find {args.hermes!r} on PATH", file=sys.stderr)
        return 2

    expected = count_skills(ROOT) or None
    tmp = Path(tempfile.mkdtemp(prefix="pstack-install-smoke-"))
    home = tmp / "home"
    home.mkdir(parents=True)
    env = {**os.environ, "HERMES_HOME": str(home), "NO_COLOR": "1"}
    facts: dict[str, str] = {}
    total = 6 if args.no_lifecycle else 8

    try:
        print(f"[1/{total}] install {args.identifier}{' @ ' + args.ref[:8] if args.ref else ''}")
        install(hermes, env, args.identifier, args.ref)
        installed = find_installed(home)
        facts.update(assert_tree(installed, expected))
        if not listed(hermes, env):
            raise StepFailed("plugin is not listed after install")
        pinned_ref = args.ref or installed_commit(installed)
        if not pinned_ref:
            raise StepFailed(
                "installed tree is not a git checkout, so there is no commit to re-pin; "
                "pass --ref <sha> explicitly"
            )

        print(f"[2/{total}] hermes plugins doctor --ci")
        doctor = run([hermes, "plugins", "doctor", PLUGIN_NAME, "--ci"], env=env)[1]
        facts["doctor"] = next(
            (ln.strip() for ln in doctor.splitlines() if "manifest:" in ln), "ok"
        )

        if args.no_lifecycle:
            print(f"[3/{total}] lifecycle skipped (--no-lifecycle)")
        else:
            print(f"[3/{total}] remove {PLUGIN_NAME}")
            run([hermes, "plugins", "remove", PLUGIN_NAME], env=env)
            assert_absent(home)
            if listed(hermes, env):
                raise StepFailed("plugin is still listed after remove")
            facts["remove"] = "directory and listing entry gone"

            print(f"[4/{total}] reinstall pinned @ {pinned_ref[:8]}")
            install(hermes, env, args.identifier, pinned_ref)
            facts.update(assert_tree(find_installed(home), expected))
            run([hermes, "plugins", "doctor", PLUGIN_NAME, "--ci"], env=env)
            facts["reinstall"] = f"pinned at {pinned_ref[:8]}"

            print(f"[5/{total}] hermes plugins update")
            rc, out = run([hermes, "plugins", "update", PLUGIN_NAME], env=env, allow_fail=True)
            if rc != 0:
                lowered = out.lower()
                if not any(word in lowered for word in ("pin", "--ref", "force", "commit")):
                    tail = out.strip().splitlines()[-6:]
                    raise StepFailed(
                        "update failed without the documented pinned-install reason:\n  "
                        + "\n  ".join(tail)
                    )
                facts["update"] = "refused, pinned install (documented)"
            else:
                facts["update"] = "applied"
            run([hermes, "plugins", "doctor", PLUGIN_NAME, "--ci"], env=env)
            facts.update(assert_tree(find_installed(home), expected))

        if args.validate:
            label = f"[{5 if args.no_lifecycle else 6}/{total}]"
            print(f"{label} validate.py --require-gold against the installed tree")
            out = run(
                [
                    sys.executable,
                    args.validate,
                    "--package",
                    str(find_installed(home)),
                    "--require-gold",
                ],
                env=env,
            )[1]
            facts["gold"] = next(
                (ln.strip() for ln in out.splitlines() if "skill_count" in ln), "passed"
            )
    except StepFailed as exc:
        print(f"\nFAIL {exc}", file=sys.stderr)
        print(f"     temp home: {home}{'' if args.keep else ' (removed)'}", file=sys.stderr)
        if not args.keep:
            shutil.rmtree(tmp, ignore_errors=True)
        return 1

    print("\nPASS install lifecycle")
    for key, value in facts.items():
        print(f"  {key}: {value}")
    if args.keep:
        print(f"  home: {home}")
    else:
        shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
