#!/usr/bin/env python3
"""Installed-user smoke test (evals tier 4).

Installs the published package into a throwaway ``HERMES_HOME`` and proves the
tree a user actually receives is usable: the manifest parses, the real loader
discovers every skill, the shipped root tooling survived packaging, and an
update leaves the install intact.

This is the only gate that covers the failure class behind #168 (root
``scripts/`` missing from the installed skill view) and #169 (a generated npm
lockfile breaking ``hermes plugins update``). The static gates in ``tools/``
cannot see either: they never install anything.

Usage::

    python tools/evals/install_smoke.py
    python tools/evals/install_smoke.py --ref 08db89f384c8fbf63ece78e6ec8d116dfd7b0aec
    python tools/evals/install_smoke.py --validate tools/validate.py

Needs the ``hermes`` CLI on PATH and network access for the clone. No provider
credentials: nothing here runs a model turn.

Exit codes: 0 all steps passed; 1 a step failed; 2 the runner could not start
(no hermes CLI, unusable temp home).
"""

from __future__ import annotations

import argparse
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


def run(cmd: list[str], *, env: dict[str, str], timeout: int = 600) -> str:
    """Run a command, returning combined output. Non-zero exit raises StepFailed."""
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, env=env, cwd=str(ROOT),
        )
    except FileNotFoundError as exc:
        raise StepFailed(f"cannot run {cmd[0]!r}: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise StepFailed(f"{' '.join(cmd)} timed out after {timeout}s") from exc
    out = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        tail = out.strip().splitlines()[-12:]
        raise StepFailed(f"{' '.join(cmd)} exited {proc.returncode}:\n  " + "\n  ".join(tail))
    return out


def find_installed(home: Path) -> Path:
    """Locate the installed plugin directory under the temp HERMES_HOME."""
    for candidate in (home / "plugins" / PLUGIN_NAME,):
        if (candidate / "plugin.json").is_file():
            return candidate
    for manifest in home.rglob("plugin.json"):
        if manifest.parent.name == PLUGIN_NAME:
            return manifest.parent
    raise StepFailed(f"no installed package found under {home}")


def count_skills(root: Path) -> int:
    return sum(1 for _ in root.glob("skills/*/SKILL.md"))


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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hermes", default="hermes", help="hermes executable (default: hermes)")
    ap.add_argument("--identifier", default="iap/pstack-hermes", help="install target: owner/repo or Git URL")
    ap.add_argument("--ref", default="", help="pin the install to one 40-character commit SHA")
    ap.add_argument("--validate", default="", help="path to tools/validate.py to run against the installed tree")
    ap.add_argument("--skip-update", action="store_true", help="skip the hermes plugins update step")
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
    try:
        install_cmd = [hermes, "plugins", "install", args.identifier, "--enable", "--yes-deps"]
        if args.ref:
            install_cmd += ["--ref", args.ref]
        print(f"[1/5] install {args.identifier}{' @ ' + args.ref[:8] if args.ref else ''}")
        run(install_cmd, env=env)

        print("[2/5] hermes plugins doctor --ci")
        doctor = run([hermes, "plugins", "doctor", PLUGIN_NAME, "--ci"], env=env)
        facts["doctor"] = next((ln.strip() for ln in doctor.splitlines() if "manifest:" in ln), "ok")

        installed = find_installed(home)
        print(f"[3/5] assert installed tree at {installed}")
        facts.update(assert_tree(installed, expected))

        if args.validate:
            print("[4/5] validate.py --require-gold against the installed tree")
            out = run([sys.executable, args.validate, "--package", str(installed), "--require-gold"], env=env)
            facts["gold"] = next((ln.strip() for ln in out.splitlines() if "skill_count" in ln), "passed")
        else:
            print("[4/5] skipped validate.py (pass --validate to run it)")

        if args.skip_update:
            print("[5/5] skipped update (--skip-update)")
        else:
            print("[5/5] hermes plugins update, then doctor again")
            run([hermes, "plugins", "update", PLUGIN_NAME], env=env)
            run([hermes, "plugins", "doctor", PLUGIN_NAME, "--ci"], env=env)
            facts.update(assert_tree(find_installed(home), expected))
    except StepFailed as exc:
        print(f"\nFAIL {exc}", file=sys.stderr)
        print(f"     temp home: {home}{'' if args.keep else ' (removed)'}", file=sys.stderr)
        if args.keep:
            return 1
        shutil.rmtree(tmp, ignore_errors=True)
        return 1

    print("\nPASS install smoke")
    for key, value in facts.items():
        print(f"  {key}: {value}")
    if args.keep:
        print(f"  home: {home}")
    else:
        shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
