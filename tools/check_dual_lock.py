#!/usr/bin/env python3
"""Dual-lock consistency gate (#169).

hermes installs Node deps via `npm ci`, so the shipped package-lock.json
must carry the same resolved versions as bun.lock. This check fails when
a direct dependency's version differs between the two locks, so a
bun-only bump cannot desync the npm side silently.

Usage: check_dual_lock.py [--root DIR]
Exit: 0 dual locks agree; 1 mismatch; 2 unreadable input.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUN_ENTRY_RE = re.compile(r'"([^"]+)":\s*\[\s*"[^"]+@([^",]+)"')


def direct_deps(root: Path) -> dict[str, str]:
    manifest = json.loads((root / "package.json").read_text(encoding="utf-8"))
    deps = dict(manifest.get("dependencies", {}))
    deps.update(manifest.get("devDependencies", {}))
    return deps


def bun_versions(root: Path) -> dict[str, str]:
    text = (root / "bun.lock").read_text(encoding="utf-8")
    return dict(BUN_ENTRY_RE.findall(text))


def npm_versions(root: Path) -> dict[str, str]:
    lock = json.loads((root / "package-lock.json").read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for key, entry in lock.get("packages", {}).items():
        if not key.startswith("node_modules/"):
            continue
        name = key[len("node_modules/"):]
        # Root entries are either "pkg" or "@scope/pkg" (one slash for a
        # scoped name); nested node_modules entries carry more segments.
        if name.count("/") <= (1 if name.startswith("@") else 0):
            out[name] = entry.get("version", "")
    return out


def check(root: Path) -> tuple[int, list[str]]:
    try:
        deps = direct_deps(root)
        bun = bun_versions(root)
        npm = npm_versions(root)
    except (OSError, ValueError) as exc:
        return 2, [f"dual-lock: unreadable input: {exc}"]
    problems = []
    for name in sorted(deps):
        if name not in bun:
            problems.append(f"dual-lock: {name} missing from bun.lock")
        if name not in npm:
            problems.append(f"dual-lock: {name} missing from package-lock.json")
        if name in bun and name in npm and bun[name] != npm[name]:
            problems.append(
                f"dual-lock: {name} bun {bun[name]} != npm {npm[name]} "
                "(regenerate package-lock.json)"
            )
    return (1 if problems else 0), problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=str(ROOT))
    args = ap.parse_args(argv)
    code, problems = check(Path(args.root).resolve())
    for line in problems:
        print(line, file=sys.stderr)
    if code == 0:
        print("dual-lock: bun.lock and package-lock.json agree")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
