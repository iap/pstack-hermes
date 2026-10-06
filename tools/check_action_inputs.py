#!/usr/bin/env python3
"""Fail when a step passes a `with:` key the action does not declare.

The runner treats an unrecognized input as a warning, not an error: it logs
"Unexpected input(s) 'X'" and silently ignores the value. That is how
`.github/workflows/labeler.yml` shipped `syncLabels: true` against an action
whose input id is `sync-labels` - label sync stayed off while the step comment
promised it, and no gate noticed. Verified against the other gates by
reintroducing the exact defect: `actionlint` exits 0 (it cannot read remote
action metadata) and the whole pytest suite passes unchanged. This is the gate
for that class: a silent misconfiguration that only the live runner log showed.

Resolution rules:
- local actions (`./...`) are read from disk;
- `docker://` references have no declared inputs and are skipped;
- everything else is fetched from raw.githubusercontent.com at the pinned ref,
  trying `action.yml` then `action.yaml`.

A fetch or parse failure for a needed action is a tool error (exit 2), never a
pass - the check cannot certify inputs it could not read. Exit codes: 0 clean,
1 findings, 2 tool error.
"""

from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
RAW_URL = "https://raw.githubusercontent.com/{repo}/{ref}/{name}"
FETCH_TIMEOUT_SECONDS = 20


def fetch_url(url: str) -> str | None:
    """Return the body, or None when the resource does not exist (404)."""
    try:
        with urllib.request.urlopen(url, timeout=FETCH_TIMEOUT_SECONDS) as resp:
            # Untrusted input, but parsed as YAML data only - never executed.
            return resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def _steps_from(doc: object) -> list[dict]:
    """All step mappings in a workflow file or a composite action file."""
    if not isinstance(doc, dict):
        return []
    runs = doc.get("runs")
    if isinstance(runs, dict) and runs.get("using") == "composite":
        return list(runs.get("steps") or [])
    steps: list[dict] = []
    for job in (doc.get("jobs") or {}).values():
        if isinstance(job, dict):
            for step in job.get("steps") or []:
                if isinstance(step, dict):
                    steps.append(step)
    return steps


def iter_usages(root: Path):
    """Yield (rel_path, step_index, uses, with_dict) for every action step."""
    targets = sorted((root / ".github" / "workflows").glob("*.y*ml"))
    targets += sorted((root / ".github" / "actions").glob("*/action.y*ml"))
    for path in targets:
        try:
            doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            yield path.relative_to(root).as_posix(), -1, None, exc
            continue
        rel = path.relative_to(root).as_posix()
        for i, step in enumerate(_steps_from(doc)):
            uses = step.get("uses")
            if isinstance(uses, str):
                yield rel, i, uses, dict(step.get("with") or {})


def declared_inputs(root: Path, uses: str, fetch) -> set[str] | None:
    """Declared input ids for `uses`, or None when it cannot be resolved.

    Raises ValueError for a malformed local reference (caller reports it).
    """
    if uses.startswith("./"):
        action_dir = root / uses[2:]
        for name in ("action.yml", "action.yaml"):
            candidate = action_dir / name
            if candidate.is_file():
                doc = yaml.safe_load(candidate.read_text(encoding="utf-8")) or {}
                return set((doc.get("inputs") or {}).keys())
        raise ValueError(f"no action.yml next to {uses}")
    if uses.startswith("docker://"):
        return None  # Docker actions declare no inputs; nothing to check.
    if "@" not in uses:
        raise ValueError(f"uses without a ref: {uses!r}")
    action, _, ref = uses.partition("@")
    parts = action.split("/")
    if len(parts) < 2:
        raise ValueError(f"not an owner/repo reference: {uses!r}")
    repo = "/".join(parts[:2])
    subdir = "/".join(parts[2:])
    prefix = f"{subdir}/" if subdir else ""
    for name in ("action.yml", "action.yaml"):
        body = fetch(RAW_URL.format(repo=repo, ref=ref, name=f"{prefix}{name}"))
        if body is not None:
            doc = yaml.safe_load(body) or {}
            return set((doc.get("inputs") or {}).keys())
    raise ValueError(f"no action.yml or action.yaml at {repo}@{ref}")


def check(root: Path = ROOT, fetch=fetch_url) -> tuple[int, list[str]]:
    """Run the check; return (exit_code, report lines)."""
    report: list[str] = []
    failures = 0
    tool_errors = 0
    resolved: dict[tuple[str, str], set[str] | None] = {}

    for rel, index, uses, payload in iter_usages(root):
        if index < 0:
            report.append(f"error: {rel}: unparseable YAML: {payload}")
            tool_errors += 1
            continue
        if uses is None:
            continue
        cache_key = uses
        if cache_key not in resolved:
            try:
                resolved[cache_key] = declared_inputs(root, uses, fetch)
            except (ValueError, urllib.error.URLError, OSError) as exc:
                report.append(f"error: {rel} step[{index}]: cannot resolve {uses}: {exc}")
                resolved[cache_key] = False  # sentinel: unresolved
                tool_errors += 1
        declared = resolved[cache_key]
        if declared is False:
            continue
        if declared is None:
            report.append(f"skip: {rel} step[{index}]: {uses} (no inputs concept)")
            continue
        unknown = sorted(k for k in payload if k not in declared)
        if unknown:
            failures += 1
            report.append(
                f"FAIL: {rel} step[{index}]: {uses} does not declare "
                f"{', '.join(repr(k) for k in unknown)} "
                f"(declared: {', '.join(sorted(declared)) or 'none'})"
            )

    if failures:
        return 1, report
    if tool_errors:
        return 2, report
    return 0, report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="check_action_inputs.py", description=__doc__)
    ap.add_argument("--root", type=Path, default=ROOT, help="repository root")
    args = ap.parse_args(argv)
    code, report = check(args.root)
    stream = sys.stderr if code else sys.stdout
    for line in report:
        print(line, file=stream)
    if code == 0:
        print("action inputs: every with: key is declared by its action")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
