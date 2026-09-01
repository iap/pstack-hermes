#!/usr/bin/env python3
"""Validation harness for the converted pstack -> hermes agent-plugins-v1 package.

Layers:
  [1] Static manifest + structure checks (pure stdlib; mirrors hermes_cli/agent_plugins.py rules)
  [2] Skill frontmatter checks (name == dir name, kebab-case, description 1..1024)
  [3] Encoding checks (no BOM, no CRLF in any normalized text file)
  [4] GOLD check: the REAL hermes loader (read_agent_plugin_manifest) via the hermes venv python
  [5] GOLD+ check: full load_agent_plugin() discovery (counts skills, surfaces per-skill diagnostics)
  [6] READ-ONLY CLI attempt: `hermes.exe plugins doctor <pkg> --ci` (verbatim capture; errors are
      findings to record, not package failures — the doctor signature is verified in parallel)

Usage: python validate.py [--package <package-dir>]
Exit codes: 0 = all hard checks + GOLD passed; 1 = hard failure; 2 = degraded (GOLD unavailable,
static checks passed).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent  # tools/
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_PACKAGE = REPO_ROOT / "pstack"

HERMES_SRC = Path(r"%LOCALAPPDATA%\hermes\hermes-agent")
VENV_PY = HERMES_SRC / ".venv" / "Scripts" / "python.exe"
VENV_HERMES = HERMES_SRC / ".venv" / "Scripts" / "hermes.exe"


def expected_count(pkg: Path) -> int:
    """Expected skill count per the converter's discovery rule:
    immediate children of <pkg>/skills/ containing a SKILL.md."""
    return sum(1 for d in (pkg / "skills").iterdir()
               if d.is_dir() and (d / "SKILL.md").is_file())


def expected_principles(pkg: Path) -> int:
    return sum(1 for d in (pkg / "skills").iterdir()
               if d.is_dir() and d.name.startswith("principle-")
               and (d / "SKILL.md").is_file())

SCHEMA_URL = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
WHITELIST = {"$schema", "name", "version", "description", "author", "homepage",
             "repository", "license", "keywords", "extensions"}
MANIFEST_NAME_RE = re.compile(r"^(?!.*(?:--|\.\.))[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$")
SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

TEXT_SUFFIXES = {".md", ".markdown", ".txt", ".yaml", ".yml", ".json", ".toml",
                 ".ts", ".tsx", ".mjs", ".js", ".cjs", ".py", ".sh", ".bash", ".ps1",
                 ".csv", ".tsv", ".lock", ".cfg", ".ini", ".html", ".css"}
# Filenames normalize_text() touches even without a text suffix (mirrors convert.py TEXT_EXTS).
TEXT_NAMES = {".gitignore", ".build-provenance.txt"}


class Report:
    def __init__(self) -> None:
        self.passed: list[str] = []
        self.failed: list[str] = []
        self.notes: list[str] = []

    def ok(self, msg: str) -> None:
        self.passed.append(msg)

    def fail(self, msg: str) -> None:
        self.failed.append(msg)

    def note(self, msg: str) -> None:
        self.notes.append(msg)


def parse_frontmatter(text: str):
    """Minimal stdlib frontmatter reader: returns (fields|None, error|None)."""
    if not text.startswith("---\n"):
        return None, "no frontmatter block at file start"
    end = text.find("\n---", 4)
    if end == -1:
        return None, "frontmatter block unterminated"
    lines = text[4:end].split("\n")
    fields: dict[str, str] = {}
    i = 0
    while i < len(lines):
        m = re.match(r"^([A-Za-z0-9_-]+):(.*)$", lines[i])
        if not m:
            i += 1
            continue
        key, rest = m.group(1), m.group(2).strip()
        if rest in (">", ">-", "|", "|+", "|-"):
            i += 1
            buf: list[str] = []
            while i < len(lines) and (lines[i].startswith((" ", "\t")) or lines[i] == ""):
                if lines[i].strip():
                    buf.append(lines[i].strip())
                i += 1
            fields[key] = (" " if rest.startswith(">") else "\n").join(buf)
            continue
        if len(rest) >= 2 and rest[0] == rest[-1] and rest[0] in "'\"":
            rest = rest[1:-1]
        fields[key] = rest
        i += 1
    return fields, None


def check_manifest(pkg: Path, rep: Report) -> dict:
    p = pkg / "plugin.json"
    if not p.is_file():
        rep.fail("root plugin.json missing")
        return {}
    raw = p.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        rep.fail("root plugin.json has a UTF-8 BOM")
    if b"\r\n" in raw:
        rep.fail("root plugin.json contains CRLF")
    try:
        m = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        rep.fail(f"root plugin.json is not valid UTF-8 JSON: {exc}")
        return {}
    if not isinstance(m, dict):
        rep.fail("root plugin.json is not a JSON object")
        return {}
    if m.get("$schema") != SCHEMA_URL:
        rep.fail(f"$schema must be exactly {SCHEMA_URL!r}, got {m.get('$schema')!r}")
    else:
        rep.ok("$schema exact-match agent-plugins.org v1")
    unknown = sorted(set(m) - WHITELIST)
    if unknown:
        rep.fail(f"manifest has non-whitelisted fields (loader would emit ignored-field diagnostics): {unknown}")
    else:
        rep.ok(f"manifest keys subset of 10-field whitelist (fields present: {len(m)})")
    name = m.get("name")
    if not isinstance(name, str) or not (1 <= len(name) <= 64) or not MANIFEST_NAME_RE.match(name):
        rep.fail(f"manifest name fails loader rules: {name!r}")
    else:
        rep.ok(f"manifest name valid: {name!r}")
    for k in ("version", "description", "homepage", "repository", "license"):
        if k in m and not isinstance(m[k], str):
            rep.fail(f"manifest {k} must be a string, got {type(m[k]).__name__}")
    if not m.get("description"):
        rep.note("manifest description empty/absent (loader tolerates but docs suffer)")
    kw = m.get("keywords")
    if kw is not None and not (isinstance(kw, list) and all(isinstance(x, str) for x in kw)):
        rep.fail("manifest keywords must be an array of strings")
    au = m.get("author")
    if au is not None and not (isinstance(au, dict) and set(au) <= {"name", "email", "url"}
                               and all(isinstance(v, str) for v in au.values())):
        rep.fail("manifest author must be an object with only string name/email/url")
    if isinstance(au, dict) and au.get("name") == "Lauren Tan":
        rep.ok("manifest author preserved: Lauren Tan")
    return m


def check_skills(pkg: Path, rep: Report) -> None:
    skills_dir = pkg / "skills"
    if not skills_dir.is_dir():
        rep.fail("skills/ directory missing")
        return
    children = sorted(d for d in skills_dir.iterdir() if d.is_dir())
    no_skill_md = [d.name for d in children if not (d / "SKILL.md").is_file()]
    if no_skill_md:
        rep.fail(f"skills/ immediate children without SKILL.md (loader would skip them): {no_skill_md}")
    nested = sorted(str(p.relative_to(pkg)) for p in skills_dir.glob("*/*/SKILL.md"))
    if nested:
        rep.fail(f"nested SKILL.md found (loader sees immediate children only): {nested}")
    else:
        rep.ok("no nested skill directories under skills/")
    loaded, bad_name, bad_desc = [], [], []
    principles = []
    seen_casefold: dict[str, str] = {}
    for d in children:
        if not (d / "SKILL.md").is_file():
            continue
        key = d.name.casefold()
        if key in seen_casefold:
            rep.fail(f"case-insensitive dir collision on Windows: {d.name} vs {seen_casefold[key]}")
        seen_casefold[key] = d.name
        fm, err = parse_frontmatter((d / "SKILL.md").read_text(encoding="utf-8", errors="replace"))
        if fm is None:
            rep.fail(f"skills/{d.name}/SKILL.md: {err}")
            continue
        if fm.get("name") != d.name or not SKILL_NAME_RE.match(fm.get("name", "")):
            bad_name.append(f"{d.name}: name={fm.get('name')!r}")
        desc = fm.get("description", "")
        if not desc or not (1 <= len(desc) <= 1024):
            bad_desc.append(f"{d.name}: description length={len(desc)}")
        loaded.append(d.name)
        if d.name.startswith("principle-"):
            principles.append(d.name)
    if bad_name:
        rep.fail(f"frontmatter name != dir name / not kebab-case: {bad_name}")
    else:
        rep.ok(f"all {len(loaded)} skills: frontmatter name == dir name, kebab-case")
    if bad_desc:
        rep.fail(f"description missing or >1024 chars: {bad_desc}")
    else:
        rep.ok(f"all {len(loaded)} skills: description present, 1..1024 chars")
    workflow = [n for n in loaded if not n.startswith("principle-")]
    rep.note(f"skills discovered: {len(loaded)} "
             f"({len(workflow)} workflow/mode + {len(principles)} principle-*)")
    expected, exp_principles = expected_count(pkg), expected_principles(pkg)
    if len(loaded) != expected or len(principles) != exp_principles or len(workflow) != expected - exp_principles:
        rep.fail(f"expected {expected} loaded skills ({expected - exp_principles} workflow/mode + "
                 f"{exp_principles} principle), got {len(loaded)} ({len(workflow)} + {len(principles)})")
    benny = sorted(str(p.relative_to(pkg)) for p in (pkg / "automations").glob("benny/skills/*/SKILL.md")) if (pkg / "automations").is_dir() else []
    if benny or (pkg / "automations").exists():
        rep.fail("F-publish: automations/ present — excluded by publisher contract (install-scanner persistence verdict)")
    else:
        rep.ok("F-publish: automations/benny excluded (install-scanner persistence verdict)")
    if "make-bot-ui" in loaded:
        rep.fail("F-publish: make-bot-ui present — excluded by publisher contract (privilege-escalation scan, F33)")
    else:
        rep.ok("F-publish: make-bot-ui excluded (privilege-escalation scan, F33)")
    total_skill_md = len(list(pkg.glob("skills/*/SKILL.md")))
    rep.note(f"SKILL.md files on disk: {total_skill_md} (expected {expected})")
    if total_skill_md != expected:
        rep.fail(f"expected {expected} SKILL.md on disk, found {total_skill_md}")


def check_encoding(pkg: Path, rep: Report) -> None:
    bom_files, crlf_files, checked = [], [], 0
    for p in pkg.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in TEXT_SUFFIXES and p.name not in TEXT_NAMES:
            continue
        data = p.read_bytes()
        checked += 1
        if data.startswith(b"\xef\xbb\xbf"):
            bom_files.append(str(p.relative_to(pkg)))
        if b"\r\n" in data:
            crlf_files.append(str(p.relative_to(pkg)))
    if bom_files:
        rep.fail(f"files with UTF-8 BOM: {bom_files}")
    else:
        rep.ok(f"no BOM in any of {checked} text files")
    if crlf_files:
        rep.fail(f"files with CRLF: {crlf_files}")
    else:
        rep.ok(f"no CRLF in any of {checked} text files")


def check_layout(pkg: Path, rep: Report) -> None:
    for rel, label in [("agents", "agents/ (expected-ignored by hermes portable path)"),
                       (".cursor-plugin/plugin.json", ".cursor-plugin/plugin.json (Cursor dual-load manifest)"),
                       ("README.md", "README.md"),
                       (".build-provenance.txt", ".build-provenance.txt")]:
        if (pkg / rel).exists():
            rep.ok(f"present: {label}")
        else:
            rep.fail(f"missing: {label}")
    # LICENSE moved to the repo root (repo layout v2); either location satisfies.
    if (pkg / "LICENSE").exists():
        rep.ok("present: LICENSE (package)")
    elif (REPO_ROOT / "LICENSE").exists():
        rep.ok("present: LICENSE (repo root)")
    else:
        rep.fail("missing: LICENSE")
    if (pkg / "automations").exists():
        rep.fail("F-publish: automations/ present (must be excluded)")
    agents_files = sorted(p.name for p in (pkg / "agents").glob("*")) if (pkg / "agents").is_dir() else []
    rep.note(f"agents/ files: {agents_files}")
    if len(agents_files) != 2:
        rep.fail(f"expected 2 agent files, found {agents_files}")


def check_phase1(pkg: Path, rep: Report) -> None:
    """Phase-1 hygiene checks: R1 index generation, F16 slug override, F10-F12 portability."""
    # R1: the shipped index must equal what the leaves generate
    try:
        sys.path.insert(0, str(SCRIPT_DIR))
        from convert import build_principles_index  # noqa: PLC0415
        generated, drift = build_principles_index(pkg / "skills")
        if drift:
            rep.fail(f"principles index generation reported: {drift}")
        pm = pkg / "skills" / "poteto-mode" / "SKILL.md"
        text = pm.read_text(encoding="utf-8")
        start = text.find("## Principles\n\nRead the leaf skill")
        end = text.find("## Autonomy", start)
        if start == -1 or end == -1:
            rep.fail("poteto-mode/SKILL.md: principles block anchors missing")
        elif text[start:end].rstrip("\n") != generated.rstrip("\n"):
            rep.fail("R1: shipped principles index does NOT match the leaves (drift reintroduced)")
        else:
            rep.ok("R1: poteto-mode principles index == leaf-generated (single source of truth)")
    except Exception as exc:  # import or generation failure is itself a finding
        rep.fail(f"R1 check could not run: {exc}")

    # F16: check-plan.mjs must be env-overridable
    cp = pkg / "skills" / "poteto-mode" / "scripts" / "check-plan.mjs"
    if cp.is_file():
        cp_text = cp.read_text(encoding="utf-8")
        if "process.env.PSTACK_FAST_LANE" in cp_text:
            rep.ok("F16: check-plan.mjs lane slug env-overridable (PSTACK_FAST_LANE)")
        else:
            rep.fail("F16: check-plan.mjs still hardcodes the lane slug")

    # F16: the multi-phase-plan template must document the override
    mp = pkg / "skills" / "poteto-mode" / "playbooks" / "multi-phase-plan.md"
    if mp.is_file():
        mp_text = mp.read_text(encoding="utf-8")
        if "PSTACK_FAST_LANE" in mp_text and "per the boot recipe" in mp_text:
            rep.ok("F16: multi-phase-plan template keeps the invariant sentence and documents the override")
        else:
            rep.fail("F16: multi-phase-plan template lost the invariant sentence or the override note")

    # F10-F12: worktree-audit.sh must use portable helpers, no unguarded BSD forms
    wa = pkg / "skills" / "poteto-mode" / "scripts" / "worktree-audit.sh"
    if wa.is_file():
        wa_text = wa.read_text(encoding="utf-8")
        bad = [s for s in ("stat -f '%m %N'", 'date -r "$last_ts"', "awk '/^worktree /{print $2}") if s in wa_text]
        good = [s for s in ("stat_mtime", "date_epoch") if s in wa_text]
        if bad:
            rep.fail(f"F10-F12: BSD-only constructs survived in worktree-audit.sh: {bad}")
        elif len(good) < 2:
            rep.fail("F10-F12: portable helpers missing from worktree-audit.sh")
        else:
            rep.ok("F10-F12: worktree-audit.sh portable (stat_mtime/date_epoch, full-path awk)")


    # Phase-2A: delegation translation must be complete
    cursor_tokens = ("subagent_type", "generalPurpose", "AskQuestion", "run_in_background")
    stragglers = []
    for p in (pkg / "skills").rglob("*.md"):
        t = p.read_text(encoding="utf-8", errors="replace")
        for tok in cursor_tokens:
            if tok in t:
                stragglers.append(f"{p.relative_to(pkg)}:{tok}")
    if stragglers:
        rep.fail(f"Phase-2A: Cursor delegation tokens remain: {stragglers}")
    else:
        rep.ok("Phase-2A: no Cursor delegation tokens in any skill")
    pm_text = (pkg / "skills" / "poteto-mode" / "SKILL.md").read_text(encoding="utf-8")
    if "delegate_task" in pm_text:
        rep.ok("Phase-2A: poteto-mode Subagents section uses delegate_task")
    else:
        rep.fail("Phase-2A: poteto-mode has no delegate_task phrasing")

    # T8: factual fixes from the hermes deep review
    t8_bad = []
    t8_patterns = {"strips MCP": "readonly-MCP rationale",
                   'environment: "local"': "swarm cloud param",
                   "cloud_base_branch": "swarm cloud param",
                   "Use Glob": "Cursor tool name",
                   "../principle-guard-the-context-window/SKILL.md)": "relative skill link"}
    for p in (pkg / "skills").rglob("*.md"):
        t = p.read_text(encoding="utf-8", errors="replace")
        for tok, label in t8_patterns.items():
            if tok in t:
                t8_bad.append(f"{p.relative_to(pkg)}:{label}")
    sp_note = (pkg / "skills" / "why" / "references" / "source-playbook.md")
    if sp_note.is_file() and "Cursor MCP examples" not in sp_note.read_text(encoding="utf-8"):
        t8_bad.append("why/references/source-playbook.md:missing adaptation note")
    if t8_bad:
        rep.fail(f"T8: unresolved constructs: {t8_bad}")
    else:
        rep.ok("T8: readonly-MCP rationale, swarm params, tool names, doc links all fixed")

    # T9/T10: hermes-native discovery + config
    t9_bad = []
    t9_toks = {"~/.cursor/projects": "Cursor transcript path",
               "available-tools map": "Cursor MCP discovery",
               "agent-transcripts": "Cursor transcripts dir",
               "ls -t <": "Cursor ls recipe",
               "create-skill": "Cursor skill-creation ref"}
    for p in (pkg / "skills").rglob("*.md"):
        t = p.read_text(encoding="utf-8", errors="replace")
        for tok, label in t9_toks.items():
            if tok in t:
                t9_bad.append(f"{p.relative_to(pkg)}:{tok} ({label})")
    if t9_bad:
        rep.fail(f"T9: Cursor discovery tokens remain: {t9_bad}")
    else:
        rep.ok("T9: discovery sections hermes-native (no Cursor tokens)")
    cfg = pkg / "config" / "models.json"
    if not cfg.is_file():
        rep.fail("T10: config/models.json missing")
    else:
        try:
            roles = json.loads(cfg.read_text(encoding="utf-8")).get("roles", {})
            if len(roles) == 18 and all("inherit-parent" in str(v) for v in roles.values()):
                rep.ok(f"T10: config/models.json present, {len(roles)} roles, inherit-parent defaults")
            else:
                rep.fail("T10: config/models.json shape unexpected")
        except Exception as exc:
            rep.fail(f"T10: config/models.json unparseable: {exc}")

    # G1: delegation escape hatch present in both files
    g1_targets = [pkg / "skills" / "poteto-mode" / "playbooks" / "feature.md",
                  pkg / "skills" / "poteto-mode" / "SKILL.md"]
    g1_missing = [str(p.relative_to(pkg)) for p in g1_targets
                  if "Exception (hermes port)" not in p.read_text(encoding="utf-8")]
    if g1_missing:
        rep.fail(f"G1: escape hatch missing in {g1_missing}")
    else:
        rep.ok("G1: delegation escape hatch present (in-thread + independent delegate review)")

    # F-publish: no scanner-flagged constructs anywhere in the shipped package
    flagged = []
    for p in pkg.rglob("*"):
        if not p.is_file():
            continue
        try:
            t = p.read_text(encoding="utf-8")
        except Exception:
            continue
        if "tailscale.com/install.sh" in t:
            flagged.append(str(p.relative_to(pkg)) + " (privilege: curl|sudo sh)")
        elif "FOR_AGENTS.md" in t:
            flagged.append(str(p.relative_to(pkg)) + " (persistence: copy-instructions)")
    if flagged:
        rep.fail(f"F-publish: scanner-flagged constructs present: {flagged}")
    else:
        rep.ok("F-publish: no scanner-flagged constructs (tailscale install.sh, FOR_AGENTS.md) in package")


def subprocess_env() -> dict:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"  # never write .pyc into the hermes install dir
    return env


def gold_manifest_check(pkg: Path) -> dict:
    """[4] Run the REAL hermes loader manifest validation via its venv python."""
    if not VENV_PY.is_file():
        return {"status": "unavailable", "reason": f"venv python not found: {VENV_PY}"}
    code = (
        "import json, sys\n"
        f"sys.path.insert(0, {json.dumps(str(HERMES_SRC))})\n"
        "from hermes_cli.agent_plugins import read_agent_plugin_manifest\n"
        f"d, diag = read_agent_plugin_manifest({json.dumps(str(pkg))})\n"
        "print(json.dumps({'data': d, 'diagnostics': [getattr(x, 'message', str(x)) for x in diag]}, indent=2, default=str))\n"
    )
    try:
        run = subprocess.run([str(VENV_PY), "-c", code], capture_output=True,
                             text=True, timeout=120, env=subprocess_env())
    except Exception as exc:
        return {"status": "error", "reason": f"subprocess failed: {exc}"}
    result: dict = {"cmd": [str(VENV_PY), "-c", "<read_agent_plugin_manifest snippet>"],
                    "exit_code": run.returncode, "stderr_tail": run.stderr[-2000:]}
    try:
        parsed = json.loads(run.stdout)
        result["parsed"] = parsed
        result["status"] = "ok" if run.returncode == 0 else "nonzero-exit"
    except Exception:
        result["stdout_tail"] = run.stdout[-2000:]
        result["status"] = "import-failed" if ("Traceback" in run.stderr) else "no-json-stdout"
    return result


def gold_load_check(pkg: Path, data_root: Path) -> dict:
    """[5] Full load_agent_plugin(): discovers skills + mcp, returns per-skill diagnostics."""
    if not VENV_PY.is_file():
        return {"status": "unavailable", "reason": f"venv python not found: {VENV_PY}"}
    data_root.mkdir(parents=True, exist_ok=True)
    code = (
        "import json, sys, dataclasses\n"
        f"sys.path.insert(0, {json.dumps(str(HERMES_SRC))})\n"
        "from hermes_cli.agent_plugins import load_agent_plugin\n"
        f"p = load_agent_plugin({json.dumps(str(pkg))}, {json.dumps(str(data_root))})\n"
        "skills = getattr(p, 'skills', []) or []\n"
        "try:\n"
        "    payload = dataclasses.asdict(p)\n"
        "except Exception:\n"
        "    payload = {k: str(v) for k, v in vars(p).items()}\n"
        "diag = [str(getattr(x, 'scope', '')) + ': ' + str(getattr(x, 'message', str(x)))\n"
        "        for x in (getattr(p, 'diagnostics', None) or [])]\n"
        "print(json.dumps({'name': getattr(p, 'name', None), 'skill_count': len(skills),\n"
        "                  'skill_names': sorted(str(getattr(s, 'name', s)) for s in skills),\n"
        "                  'mcp_server_count': len(getattr(p, 'mcp_servers', []) or []),\n"
        "                  'diagnostics': diag, 'data': payload}, indent=2, default=str))\n"
    )
    try:
        run = subprocess.run([str(VENV_PY), "-c", code], capture_output=True,
                             text=True, timeout=120, env=subprocess_env())
    except Exception as exc:
        return {"status": "error", "reason": f"subprocess failed: {exc}"}
    result: dict = {"cmd": [str(VENV_PY), "-c", "<load_agent_plugin snippet>"],
                    "exit_code": run.returncode, "stderr_tail": run.stderr[-4000:]}
    try:
        parsed = json.loads(run.stdout)
        result["parsed"] = parsed
        result["status"] = "ok" if run.returncode == 0 else "nonzero-exit"
    except Exception:
        result["stdout_tail"] = run.stdout[-2000:]
        result["status"] = "import-failed" if ("Traceback" in run.stderr) else "no-json-stdout"
    return result


def cli_doctor(pkg: Path) -> dict:
    """[6] READ-ONLY attempt at the hermes plugins doctor CLI. Errors = findings, not failures."""
    if not VENV_HERMES.is_file():
        return {"status": "unavailable", "reason": f"hermes.exe not found: {VENV_HERMES}"}
    cmd = [str(VENV_HERMES), "plugins", "doctor", str(pkg), "--ci"]
    try:
        run = subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=subprocess_env())
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "cmd": cmd, "note": "killed after 60s"}
    except Exception as exc:
        return {"status": "error", "cmd": cmd, "reason": str(exc)}
    return {"status": "ran", "cmd": cmd, "exit_code": run.returncode,
            "stdout": run.stdout, "stderr": run.stderr}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", default=str(DEFAULT_PACKAGE))
    args = ap.parse_args()
    pkg = Path(args.package).resolve()
    rep = Report()

    print(f"== validate.py ==\npackage: {pkg}\n")
    gold: dict = {"status": "unavailable", "reason": "package dir missing"}
    load: dict = {"status": "skipped", "reason": "package dir missing"}
    gold_ok = load_ok = False
    if not pkg.is_dir():
        rep.fail(f"package dir not found: {pkg}")
    else:
        check_manifest(pkg, rep)
        check_skills(pkg, rep)
        check_encoding(pkg, rep)
        check_layout(pkg, rep)
        check_phase1(pkg, rep)

        print("-- [1..3] static checks (stdlib replication of agent_plugins.py rules) --")
        for msg in rep.passed:
            print(f"  PASS  {msg}")
        for msg in rep.notes:
            print(f"  NOTE  {msg}")
        for msg in rep.failed:
            print(f"  FAIL  {msg}")

        print("\n-- [4] GOLD check: real hermes loader read_agent_plugin_manifest --")
        gold = gold_manifest_check(pkg)
        print(json.dumps(gold, indent=2, default=str))
        gold_ok = gold.get("status") == "ok" and not (gold.get("parsed", {}).get("diagnostics"))
        if gold_ok:
            print("  GOLD: manifest validated by the real loader; ZERO diagnostics.")
        elif gold.get("status") == "unavailable":
            print(f"  GOLD unavailable -> static fallback only ({gold.get('reason')})")
        else:
            print("  GOLD: see output above (diagnostics/errors recorded as findings)")

        print("\n-- [5] GOLD+ full load_agent_plugin (skill discovery) --")
        load = gold_load_check(pkg, SCRIPT_DIR / ".validate-data")
        load_ok = False
        if load.get("status") == "ok":
            parsed = load["parsed"]
            print(f"  skill_count={parsed.get('skill_count')} mcp={parsed.get('mcp_server_count')} "
                  f"diagnostics={parsed.get('diagnostics')}")
            data = parsed.get("data") or {}
            print(f"  manifest round-trip: name={data.get('name')!r} version={data.get('version')!r} "
                  f"root={data.get('root')}")
            names = parsed.get("skill_names") or []
            if parsed.get("skill_count") == expected_count(pkg) and not parsed.get("diagnostics"):
                print(f"  GOLD+: all {expected_count(pkg)} skills discovered by the real loader, "
                      "zero component diagnostics.")
            else:
                print("  GOLD+: UNEXPECTED — see skill_names/diagnostics above")
            print(f"  skill names: {names}")
        else:
            print(json.dumps(load, indent=2, default=str))

        print("\n-- [6] READ-ONLY CLI attempt: hermes plugins doctor <pkg> --ci --")
        doc = cli_doctor(pkg)
        print(json.dumps(doc, indent=2, default=str))
        if doc.get("status") == "ran" and doc.get("exit_code") != 0:
            rep.note(f"plugins doctor exited {doc.get('exit_code')} — recorded as finding (signature "
                     "being verified in parallel), not a package failure")

        load_ok = load.get("status") == "ok" \
            and load.get("parsed", {}).get("skill_count") == expected_count(pkg) \
            and not load.get("parsed", {}).get("diagnostics")

        # Optional: repo YAML structural check (only when pyyaml is available,
        # e.g. via `uv sync` dev group or CI). The package itself ships no YAML;
        # this validates the repo's CI configs, labeler, and issue templates.
        try:
            import yaml  # type: ignore
        except ImportError:
            yaml = None
        if yaml is not None:
            repo = REPO_ROOT
            gh = repo / ".github"
            ymls = sorted(gh.rglob("*.yml")) if gh.is_dir() else []
            bad_yml = []
            for y in ymls:
                try:
                    yaml.safe_load(y.read_text(encoding="utf-8"))
                except Exception as exc:
                    bad_yml.append(f"{y.name}: {str(exc)[:100]}")
            if ymls:
                print(f"\n-- [R] Repo YAML structural check ({len(ymls)} files) --")
                for b in bad_yml:
                    print(f"  YAML FAIL: {b}")
                    rep.failed.append(f"repo YAML invalid: {b}")
                if not bad_yml:
                    print(f"  PASS: all {len(ymls)} .github YAML files parse clean")

        print("\n== verdict ==")
        if rep.failed:
            print(f"HARD FAILURES: {len(rep.failed)}")
            for m in rep.failed:
                print(f"  - {m}")
        print(f"static: {'PASS' if not rep.failed else 'FAIL'}; "
              f"gold manifest: {'PASS' if gold_ok else 'FAIL/unavailable'}; "
              f"gold load: {'PASS' if load_ok else 'FAIL/unavailable'}")
        if rep.failed:
            return 1
        if not (gold_ok and load_ok):
            return 2
        return 0


if __name__ == "__main__":
    sys.exit(main())
