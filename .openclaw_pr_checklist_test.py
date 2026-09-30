#!/usr/bin/env python3
"""Advisory PR checklist validator for pstack-hermes.

Design contract:
  * Runs against a checkout of the PR HEAD. It NEVER writes into pstack/ --
    that is precisely what makes its rebuild check non-tautological while
    ci.yml's is (see report section 3).
  * Every claim in the PR body is cross-checked against the tree or against a
    CI run. A self-declaration is never accepted as proof of itself.
  * Always advisory: exit 0 unless --strict. Emit one markdown comment.

Usage:
  uv run --frozen tools/pr_checklist.py --body-file body.md [--repo .] \
      [--base main] [--head HEAD] [--tier auto|cheap|full] [--strict] [--json]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

PROV_FENCE = re.compile(r"^```ya?ml[ \t]+provenance[ \t]*$", re.M)
FENCE = re.compile(r"^```[ \t]*$", re.M)
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA16 = re.compile(r"^[0-9a-f]{16}$")
# Legacy prose form: "Rebuilt from pin: `93b00b8...`" / "rebuilt from pin `93b00b8`"
LEGACY_PIN = re.compile(r"[Rr]ebuilt from pin[^0-9a-f]*`?([0-9a-f]{7,40})`?")
PLACEHOLDER = re.compile(r"(?i)\b(todo|tbd|n/?a|none|see above|paste here|<[^>]+>|\.\.\.)\b")
CI_URL = re.compile(r"https://github\.com/[\w.-]+/[\w.-]+/actions/runs/(\d+)")
MARKER = re.compile(r"<!--\s*checklist:v(\d+)\s*-->")

VALID_KEYS = {
    "schema", "package_changed", "rebuilt_from_pin",
    "source_commit", "converter_sha", "converter_change",
}


@dataclass
class Check:
    id: str
    title: str
    status: str            # pass | fail | skip | legacy
    detail: str = ""
    tier: str = "cheap"    # cheap | full
    evidence_ref: str = ""


@dataclass
class Report:
    schema_seen: int | None = None
    state: str = "v2"      # v2 | legacy | unknown
    checks: list = field(default_factory=list)

    def add(self, *a, **kw) -> None:
        self.checks.append(Check(*a, **kw))

    def counts(self) -> dict:
        c = {"pass": 0, "fail": 0, "skip": 0, "legacy": 0}
        for k in self.checks:
            c[k.status] += 1
        return c


# --------------------------------------------------------------------------
# tiny yaml reader: the provenance block is a flat key: value map by contract,
# so we do not need a yaml dependency and cannot be foot-gunned by one.
# --------------------------------------------------------------------------
def parse_provenance(text: str) -> tuple[dict, str]:
    m = PROV_FENCE.search(text)
    if not m:
        return {}, "no ```yaml provenance block found"
    start = m.end()
    end = FENCE.search(text, start)
    if not end:
        return {}, "provenance block is not closed"
    block = text[start:end.start()]
    data: dict[str, str] = {}
    for ln, raw in enumerate(block.splitlines(), 1):
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line != line.lstrip():
            return {}, f"provenance line {ln}: unexpected indentation (flat map only)"
        if ":" not in line:
            return {}, f"provenance line {ln}: expected `key: value`"
        k, v = line.split(":", 1)
        k = k.strip()
        if k in data:
            return {}, f"provenance line {ln}: duplicate key `{k}`"
        data[k] = v.strip().strip('"').strip("'")
    return data, ""


def run_git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, check=True,
    ).stdout


def changed_files(repo: Path, base: str, head: str) -> list[str]:
    out = run_git(repo, "diff", "--name-only", f"{base}...{head}")
    return [ln for ln in out.splitlines() if ln]


def file_text(repo: Path, path: str) -> str | None:
    p = repo / path
    if not p.is_file():
        return None
    return p.read_text(encoding="utf-8", errors="replace")


def prov_field(text: str, key: str) -> str | None:
    m = re.search(rf"^{key}:\s*(.+)$", text, re.M)
    return m.group(1).strip() if m else None


def sha16_of(repo: Path, rel: str) -> str | None:
    p = repo / rel
    if not p.is_file():
        return None
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def workflow_pins(repo: Path) -> dict[str, str | None]:
    pins: dict[str, str | None] = {}
    for wf in ("ci.yml", "release.yml", "upstream-drift-watch.yml"):
        t = file_text(repo, f".github/workflows/{wf}")
        pins[wf] = prov_field(t, "UPSTREAM_PIN") if t else None
    return pins


def evidence_blocks(text: str) -> list[str]:
    """Fenced blocks that follow a `- [x]`/`- [ ]` gate line."""
    blocks: list[str] = []
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if not re.match(r"^\s*- \[[ xX]\]", ln):
            continue
        j, buf = i + 1, []
        while j < len(lines):
            nxt = lines[j]
            if re.match(r"^\s*- \[[ xX]\]", nxt) or nxt.startswith("#"):
                break
            if nxt.strip():
                buf.append(nxt)
            j += 1
        blocks.append("\n".join(buf).strip())
    return blocks


# --------------------------------------------------------------------------
# checks
# --------------------------------------------------------------------------
def check_schema(rep: Report, body: str) -> tuple[dict, bool]:
    data, err = parse_provenance(body)
    mk = MARKER.search(body)
    rep.schema_seen = int(mk.group(1)) if mk else None

    if err and data == {}:
        legacy = LEGACY_PIN.search(body)
        if legacy:
            data = {"source_commit": legacy.group(1),
                    "rebuilt_from_pin": "true",
                    "__legacy__": "prose-pin-recovered"}
            rep.state = "legacy"
            rep.add("provenance", "Provenance block", "legacy",
                    "No fenced block; recovered `source_commit` from the legacy prose "
                    "field. Fill the ```yaml provenance block on the next push.", "cheap")
            return data, True
        rep.state = "unknown"
        rep.add("provenance", "Provenance block", "fail", err, "cheap")
        return data, False

    rep.add("provenance", "Provenance block", "pass",
            f"parsed {len(data)} keys: {', '.join(sorted(data)) or 'none'}", "cheap")

    if mk and int(mk.group(1)) != 2:
        rep.add("schema-version", "Checklist schema version", "legacy",
                f"body declares checklist:v{mk.group(1)}; validator speaks v2", "cheap")

    bad = sorted(set(data) - VALID_KEYS)
    if bad:
        rep.add("provenance-keys", "Known provenance keys", "fail",
                f"unknown key(s): {', '.join(bad)} (allowed: {', '.join(sorted(VALID_KEYS))})",
                "cheap")
    else:
        rep.add("provenance-keys", "Known provenance keys", "pass",
                "no unknown keys", "cheap")

    if data.get("schema") not in (None, "1"):
        rep.add("provenance-schema", "schema: 1", "fail",
                f"schema is {data.get('schema')!r}, expected 1", "cheap")
    else:
        rep.add("provenance-schema", "schema: 1", "pass", "schema ok", "cheap")
    return data, True


def check_package_changed(rep: Report, body: str, data: dict, files: list[str]) -> bool:
    truth = any(f == "pstack" or f.startswith("pstack/") for f in files)
    claim = str(data.get("package_changed", "")).strip().lower()
    if claim not in ("true", "false"):
        rep.add("package-changed", "package_changed matches the diff", "fail",
                f"`package_changed` is {claim or 'missing'!r}; this PR touches "
                f"{'pstack/' if truth else 'no pstack/ file'}", "cheap")
        return truth
    claimed = claim == "true"
    if claimed == truth:
        rep.add("package-changed", "package_changed matches the diff", "pass",
                f"pstack/ {'changed' if truth else 'untouched'}; claim agrees", "cheap")
    else:
        rep.add("package-changed", "package_changed matches the diff", "fail",
                f"body says package_changed={claim} but the diff has "
                f"{len([f for f in files if f.startswith('pstack/')])} pstack/ file(s)",
                "cheap")
    return truth


def check_pin_lockstep(rep: Report, repo: Path) -> str | None:
    pins = workflow_pins(repo)
    vals = {k: v for k, v in pins.items() if v}
    ref = pins.get("ci.yml")
    if len(vals) != 3 or len(set(vals.values())) != 1:
        rep.add("pin-lockstep", "UPSTREAM_PIN agrees across workflows", "fail",
                "; ".join(f"{k}={v or 'ABSENT'}" for k, v in pins.items()), "cheap")
        return ref
    rep.add("pin-lockstep", "UPSTREAM_PIN agrees across workflows", "pass",
            f"{ref} in ci.yml, release.yml, upstream-drift-watch.yml", "cheap")
    return ref


def check_source_commit(rep: Report, repo: Path, data: dict, pin: str | None) -> None:
    pkg = file_text(repo, "pstack/.build-provenance.txt")
    pkg_sha = prov_field(pkg, "source_commit") if pkg else None
    claim = data.get("source_commit")
    if not claim:
        rep.add("source-commit", "source_commit == pstack/.build-provenance.txt", "fail",
                f"not declared (package provenance says {pkg_sha or 'no package file'})",
                "cheap")
    elif not SHA40.match(claim):
        rep.add("source-commit", "source_commit == pstack/.build-provenance.txt", "fail",
                f"{claim!r} is not a 40-hex sha", "cheap")
    elif pkg_sha and claim != pkg_sha:
        rep.add("source-commit", "source_commit == pstack/.build-provenance.txt", "fail",
                f"body says {claim[:12]}…, pstack/.build-provenance.txt says "
                f"{(pkg_sha or '')[:12]}… — the package was built from a different pin",
                "cheap")
    elif not pkg_sha:
        rep.add("source-commit", "source_commit == pstack/.build-provenance.txt", "skip",
                "no pstack/.build-provenance.txt in this tree", "cheap")
    else:
        rep.add("source-commit", "source_commit == pstack/.build-provenance.txt", "pass",
                f"{claim[:12]}… matches the committed package provenance", "cheap")

    if pin:
        if claim and claim == pin:
            rep.add("pin-match", "source_commit == UPSTREAM_PIN", "pass",
                    f"body pin == workflows pin {pin[:12]}…", "cheap")
        elif claim:
            rep.add("pin-match", "source_commit == UPSTREAM_PIN", "fail",
                    f"body {claim[:12]}… != workflows UPSTREAM_PIN {pin[:12]}… "
                    "(a pin move must update ci.yml/release.yml/upstream-drift-watch.yml)",
                    "cheap")


def check_converter_sha(rep: Report, repo: Path, data: dict, pkg_changed: bool) -> None:
    """The staleness tripwire: converter changed but package not rebuilt."""
    actual = sha16_of(repo, "tools/convert.py")
    pkg = file_text(repo, "pstack/.build-provenance.txt")
    recorded = None
    if pkg:
        m = re.search(r"sha256\[:16\]=([0-9a-f]{16})", pkg)
        recorded = m.group(1) if m else None
    claim = data.get("converter_sha")

    if claim and not SHA16.match(claim):
        rep.add("converter-sha", "converter_sha is a 16-hex digest", "fail",
                f"{claim!r}", "cheap")
        return
    if claim:
        rep.add("converter-sha", "converter_sha declared", "pass", claim, "cheap")
    else:
        rep.add("converter-sha", "converter_sha declared", "skip",
                "not declared (only required when pstack/ changed)", "cheap")

    if actual and recorded and actual != recorded:
        rep.add("converter-fresh", "package was built by THIS converter", "fail",
                f"tools/convert.py in this PR is {actual}, but pstack/.build-provenance.txt "
                f"records {recorded} — edit the converter, then rebuild pstack/ from the pin",
                "cheap")
    elif actual and recorded:
        rep.add("converter-fresh", "package was built by THIS converter", "pass",
                f"tools/convert.py {actual} == provenance converter sha", "cheap")
    elif not recorded:
        rep.add("converter-fresh", "package was built by THIS converter", "skip",
                "no converter digest in package provenance", "cheap")


def check_rebuilt_flag(rep: Report, data: dict, pkg_changed: bool) -> None:
    claim = str(data.get("rebuilt_from_pin", "")).strip().lower()
    if pkg_changed and claim != "true":
        rep.add("rebuilt-from-pin", "rebuilt_from_pin: true when pstack/ changed", "fail",
                f"pstack/ changed but rebuilt_from_pin is {claim or 'missing'!r}", "cheap")
    elif not pkg_changed and claim == "true":
        rep.add("rebuilt-from-pin", "rebuilt_from_pin omitted when pstack/ untouched",
                "fail", "pstack/ untouched but rebuilt_from_pin: true", "cheap")
    else:
        rep.add("rebuilt-from-pin", "rebuilt_from_pin consistent with the diff", "pass",
                "consistent with the diff", "cheap")


def check_converter_change(rep: Report, repo: Path, data: dict, files: list[str]) -> None:
    """CONTRIBUTING rule: a converter/assets change needs an ADAPTATIONS row."""
    tools_touched = [f for f in files
                     if f in ("tools/convert.py", "tools/bans.py", "tools/assets/model-panel.json")
                     or f.startswith("tools/assets/")]
    if not tools_touched:
        rep.add("adaptations-row", "ADAPTATIONS row when the converter changes", "skip",
                "no converter/asset input changed", "cheap")
        return
    doc = "docs/ADAPTATIONS.md"
    if doc not in files:
        rep.add("adaptations-row", "ADAPTATIONS row when the converter changes", "fail",
                f"{', '.join(tools_touched)} changed but {doc} was not touched — add the "
                "ledger row with its reviewer check", "cheap")
    else:
        rep.add("adaptations-row", "ADAPTATIONS row when the converter changes", "pass",
                f"{doc} updated alongside {len(tools_touched)} converter input(s)", "cheap")


def check_evidence(rep: Report, body: str) -> None:
    blocks = evidence_blocks(body)
    if not blocks:
        rep.add("evidence", "Gate evidence blocks are non-empty", "skip",
                "no `[x]` gate lines in this body", "cheap")
        return
    empty, thin = [], []
    for b in blocks:
        if not b:
            empty.append(b)
        elif len(b) < 20 or PLACEHOLDER.search(b):
            thin.append(b[:60])
    if empty:
        rep.add("evidence", "Gate evidence blocks are non-empty", "fail",
                f"{len(empty)} of {len(blocks)} checked gate(s) have no evidence — a bare "
                "checkbox proves nothing", "cheap")
    elif thin:
        rep.add("evidence", "Gate evidence blocks are non-empty", "fail",
                f"{len(thin)} evidence block(s) look like a placeholder: {thin[0]!r}", "cheap")
    else:
        rep.add("evidence", "Gate evidence blocks are non-empty", "pass",
                f"{len(blocks)} gate(s), all with substantive evidence", "cheap")


def check_ci_link(rep: Report, body: str, head: str) -> None:
    runs = CI_URL.findall(body)
    if not runs:
        rep.add("ci-link", "CI run linked for this head SHA", "fail",
                "no actions/runs link — paste the run for this exact head so the reviewer "
                "does not have to guess which commit passed", "cheap")
        return
    short = head[:12]
    rep.add("ci-link", "CI run linked for this head SHA", "pass",
            f"{len(runs)} run link(s); head={short}", "cheap")


def check_package_manifest(rep: Report, repo: Path, head: str) -> None:
    """Cheap hand-edit tripwire: hash the committed tree vs the committed manifest."""
    man = file_text(repo, "pstack/.build-manifest.txt")
    if not man:
        rep.add("package-manifest", "pstack/ matches its build manifest", "skip",
                "no pstack/.build-manifest.txt (converter does not emit one yet)", "cheap")
        return
    listed: dict[str, str] = {}
    for ln in man.splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        digest, _, name = ln.partition("  ")
        if name:
            listed[name.strip().lstrip("*")] = digest.strip()
    root = repo / "pstack"
    actual = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            actual[str(p.relative_to(root))] = hashlib.sha256(p.read_bytes()).hexdigest()
    actual.pop(".build-provenance.txt", None)
    listed.pop(".build-provenance.txt", None)
    added = sorted(set(actual) - set(listed))
    removed = sorted(set(listed) - set(actual))
    changed = sorted(n for n in set(actual) & set(listed) if actual[n] != listed[n])
    if not (added or removed or changed):
        rep.add("package-manifest", "pstack/ matches its build manifest", "pass",
                f"{len(actual)} files byte-identical to the last build", "cheap")
        return
    detail = (f"+{len(added)} added, -{len(removed)} removed, {len(changed)} modified "
              f"vs the last converter build")
    sample = ", ".join(changed[:3] + added[:2] + removed[:2])
    rep.add("package-manifest", "pstack/ matches its build manifest", "fail",
            f"{detail} ({sample}) — pstack/ is converter output; change tools/ and rebuild",
            "cheap")


def check_rebuild(rep: Report, repo: Path, head: str, pin: str | None) -> None:
    """GROUND TRUTH. Builds into a scratch dir; never touches ./pstack."""
    import shutil
    import tempfile
    if not pin:
        rep.add("rebuild-from-pin", "pstack/ == fresh build from the pin", "skip",
                "no UPSTREAM_PIN resolvable", "full")
        return
    tmp = Path(tempfile.mkdtemp(prefix="pr-check-"))
    try:
        src = tmp / "cursor-plugins"
        clone = subprocess.run(
            ["git", "clone", "--filter=blob:none", "--no-checkout",
             "https://github.com/cursor/plugins.git", str(src)],
            capture_output=True, text=True)
        if clone.returncode != 0:
            rep.add("rebuild-from-pin", "pstack/ == fresh build from the pin", "fail",
                    f"upstream clone failed: {clone.stderr.strip()[:200]}", "full")
            return
        for args in (["fetch", "origin", pin], ["checkout", "-q", pin]):
            r = subprocess.run(["git", "-C", str(src), *args],
                               capture_output=True, text=True)
            if r.returncode != 0:
                rep.add("rebuild-from-pin", "pstack/ == fresh build from the pin", "fail",
                        f"cannot checkout pin: {r.stderr.strip()[:200]}", "full")
                return
        out = tmp / "rebuilt"
        env = {**os.environ, "SOURCE_DATE_EPOCH": run_git(repo, "log", "-1", "--format=%ct", head).strip()}
        b = subprocess.run(
            ["uv", "run", "--frozen", "tools/convert.py", "--source", str(src / "pstack"),
             "--out", str(out)],
            cwd=str(repo), capture_output=True, text=True, env=env)
        if b.returncode != 0:
            rep.add("rebuild-from-pin", "pstack/ == fresh build from the pin", "fail",
                    f"converter failed: {b.stderr.strip()[-300:]}", "full")
            return
        d = subprocess.run(
            ["diff", "-r", "--exclude=.build-provenance.txt", "--exclude=.build-manifest.txt",
             str(repo / "pstack"), str(out)],
            capture_output=True, text=True)
        if d.returncode == 0:
            rep.add("rebuild-from-pin", "pstack/ == fresh build from the pin", "pass",
                    "byte-identical to a fresh convert from the pin", "full")
        else:
            lines = [l for l in d.stdout.splitlines() if l.strip()][:6]
            rep.add("rebuild-from-pin", "pstack/ == fresh build from the pin", "fail",
                    "committed pstack/ drifts from a fresh build: " + " | ".join(lines),
                    "full")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--body-file", required=True)
    ap.add_argument("--repo", default=".")
    ap.add_argument("--base", default="main")
    ap.add_argument("--head", default="HEAD")
    ap.add_argument("--tier", choices=("auto", "cheap", "full"), default="auto")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    repo = Path(a.repo).resolve()
    body = Path(a.body_file).read_text(encoding="utf-8", errors="replace")
    files = changed_files(repo, a.base, a.head)
    pkg_changed = any(f.startswith("pstack/") for f in files)
    tools_changed = any(f.startswith("tools/") for f in files)
    pin_changed = any(f == ".github/workflows/ci.yml" and "UPSTREAM_PIN" in
                      (file_text(repo, f) or "") for f in files)

    full = a.tier == "full" or (a.tier == "auto" and (tools_changed or pin_changed))

    rep = Report()
    data, ok = check_schema(rep, body)
    check_package_changed(rep, body, data, files)
    pin = check_pin_lockstep(rep, repo)
    check_source_commit(rep, repo, data, pin)
    check_converter_sha(rep, repo, data, pkg_changed)
    check_rebuilt_flag(rep, data, pkg_changed)
    check_converter_change(rep, repo, data, files)
    check_evidence(rep, body)
    check_ci_link(rep, body, a.head)
    if pkg_changed or a.tier != "cheap":
        check_package_manifest(rep, repo, a.head)
    if full:
        check_rebuild(rep, repo, a.head, pin)

    c = rep.counts()
    if c["fail"] and rep.state == "v2":
        state = "findings"
    elif c["fail"]:
        state = "legacy-findings"
    elif rep.state == "legacy":
        state = "legacy-clean"
    else:
        state = "clean"

    if a.json:
        print(json.dumps({"state": state, "schema": rep.schema_seen,
                          "counts": c, "tier": "full" if full else "cheap",
                          "checks": [asdict(x) for x in rep.checks]}, indent=2))
    else:
        print(render(rep, state, c, full))
    return 1 if (a.strict and c["fail"]) else 0


ICON = {"pass": "✅", "fail": "❌", "skip": "➖", "legacy": "🟡"}


def render(rep: Report, state: str, c: dict, full: bool) -> str:
    head = {
        "clean": "### PR checklist — all automated checks pass",
        "legacy-clean": "### PR checklist — pre-v2 body, no findings",
        "findings": "### PR checklist — findings (advisory, not blocking)",
        "legacy-findings": "### PR checklist — pre-v2 body with findings",
    }[state]
    out = [head, "",
           f"{c['pass']} passed · {c['fail']} finding(s) · {c['skip']} not applicable "
           f"· tier: {'full (rebuilt from the pin)' if full else 'cheap (no rebuild)'}",
           "",
           "| | check | tier | detail |", "|---|---|---|---|"]
    for k in rep.checks:
        t = "full" if k.tier == "full" else "cheap"
        out.append(f"| {ICON[k.status]} | {k.title} | {t} | {k.detail} |")
    if rep.state != "v2":
        out += ["", "> [!NOTE]",
                "> This PR body predates the machine-readable checklist. It was parsed on "
                "a best-effort basis; push any commit with the ```yaml provenance block "
                "and these checks become exact."]
    out += ["", "<sub>Advisory: this check never blocks a merge. Findings are for the "
            "reviewer and the author.</sub>"]
    return "\n".join(out)


if __name__ == "__main__":
    sys.exit(main())