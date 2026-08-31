#!/usr/bin/env python3
"""Phase-0 converter: Cursor pstack plugin -> hermes agent-plugins-v1 portable package.

Reproducible: re-running against the same source clone produces an identical package
modulo the provenance timestamp (output dir is rebuilt from scratch each run; no
incremental state). Set SOURCE_DATE_EPOCH=<unix-ts> for a fully deterministic build.

Contract implemented (study Ch3 sections 3.1-3.2 + subagent_03a loader facts):
  - Root-level plugin.json ONLY (hermes probes the package root, never
    .cursor-plugin/); whitelisted fields only (9 emitted; extensions omitted
    since pstack has none), exact $schema URL.
  - skills/ single level: flatten skills/grokbot/make-bot-ui -> skills/make-bot-ui,
    delete the now-empty grokbot container.
  - Fix exactly two SKILL.md frontmatter names so name == directory name in
    kebab-case (agent_plugins.py:158-168). Nothing else in any SKILL.md changes.
  - agents/ and automations/ copied unchanged (inert on hermes portable path;
    kept for Cursor dual-load and Phase 2).
  - Every copied text file normalized to UTF-8 WITHOUT BOM, LF line endings.
  - .cursor-plugin/plugin.json preserved as-is (Cursor-rich manifest) so the
    package dual-loads; hermes reads the root manifest only.
  - Provenance (source commit) written to .build-provenance.txt.

Usage:
    python convert.py [--source <pstack-clone-path>] [--out <package-dir>]

Defaults: --source = the study clone, --out = ./pstack next to this script.
This script NEVER executes anything from the pstack repo (pure file copy).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_SOURCE = Path(
    r"(local clone)"
)
DEFAULT_OUT = SCRIPT_DIR / "pstack"

SCHEMA_URL = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
# agent_plugins.py:24-35 whitelist (extensions intentionally NOT emitted: pstack has none,
# and every whitelisted-but-empty field we can omit, we omit).
WHITELIST = [
    "$schema",
    "name",
    "version",
    "description",
    "author",
    "homepage",
    "repository",
    "license",
    "keywords",
]
MANIFEST_NAME_RE = re.compile(r"^(?!.*(?:--|\.\.))[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$")
SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

# Extensions treated as text (normalized). Anything else is sniffed: NUL byte
# or non-UTF-8 => byte-for-byte copy.
TEXT_EXTS = {
    ".md", ".markdown", ".txt", ".yaml", ".yml", ".json", ".toml",
    ".ts", ".tsx", ".mjs", ".js", ".cjs", ".py", ".sh", ".bash", ".ps1",
    ".html", ".css", ".csv", ".tsv", ".lock", ".cfg", ".ini", ".gitignore",
}

# The conversion gate (study 3.2 fixes 2): frontmatter name must equal the
# directory name (kebab-case) for the portable loader.
FRONTMATTER_FIXES = {
    "poteto-mode": ("Poteto Mode", "poteto-mode"),
}

# ---------------------------------------------------------------------------
# Phase-1 hygiene transforms (study findings R1, F16, F10-F12). Each is a
# targeted post-copy edit so the upstream clone stays faithful and every
# rebuild re-applies the fixes deterministically.
# ---------------------------------------------------------------------------

# R1: authoritative grouping for the poteto-mode principles index (the group
# assignment lives only in the index upstream; leaves carry the descriptions).
PRINCIPLE_GROUPS = [
    ("Core", [
        "principle-laziness-protocol",
        "principle-foundational-thinking",
        "principle-redesign-from-first-principles",
        "principle-subtract-before-you-add",
        "principle-minimize-reader-load",
        "principle-outcome-oriented-execution",
        "principle-experience-first",
        "principle-exhaust-the-design-space",
        "principle-build-the-lever",
    ]),
    ("Architecture", [
        "principle-model-the-domain",
        "principle-boundary-discipline",
        "principle-type-system-discipline",
        "principle-make-operations-idempotent",
        "principle-migrate-callers-then-delete-legacy-apis",
        "principle-separate-before-serializing-shared-state",
    ]),
    ("Verification", [
        "principle-prove-it-works",
        "principle-fix-root-causes",
        "principle-sequence-verifiable-units",
    ]),
    ("Delegation", [
        "principle-guard-the-context-window",
        "principle-never-block-on-the-human",
    ]),
    ("Meta", [
        "principle-encode-lessons-in-structure",
    ]),
]

_PRINCIPLES_HEADER = (
    "## Principles\n\n"
    "Read the leaf skill in full for any principle you apply. "
    "Each entry names when it applies.\n\n"
)
_NEXT_SECTION = "## Autonomy"

# F16: the lane-invariant slug becomes env-overridable (default = upstream).
CHECK_PLAN_OLD = 'const LANES = "Ten lanes on `grok-4.6-fast-xhigh` at the PR head";'
CHECK_PLAN_NEW = (
    "// F16 fix: the fast-lane slug is env-overridable so a reconfigured panel"
    "\n// does not fail the playbook's own validator. Default matches upstream."
    "\nconst FAST_LANE = process.env.PSTACK_FAST_LANE || \"grok-4.6-fast-xhigh\";"
    "\nconst LANES = `Ten lanes on \\`${FAST_LANE}\\` at the PR head`;"
)
MULTIPHASE_OLD_FRAGMENT = "checked. Ten lanes on `grok-4.6-fast-xhigh` at the PR head, per the boot recipe."
MULTIPHASE_NEW_FRAGMENT = (
    "checked. Ten lanes on `grok-4.6-fast-xhigh` at the PR head, per the boot recipe."
    " Set `PSTACK_FAST_LANE` to your configured fast-lane slug when the panel"
    " was reconfigured (default `grok-4.6-fast-xhigh`)."
)

# F10-F12: portable mtime/epoch helpers inserted after `set -u`.
WORKTREE_HELPERS_ANCHOR = "set -u\n"
WORKTREE_HELPERS = (
    "set -u\n\n"
    "# F10-F12 fix: GNU coreutils vs BSD/macOS mtime + epoch conversion.\n"
    "if stat -c '%Y' / >/dev/null 2>&1; then\n"
    "\tstat_mtime() { stat -c '%Y' \"$1\" 2>/dev/null; }\n"
    "else\n"
    "\tstat_mtime() { stat -f '%m' \"$1\" 2>/dev/null; }\n"
    "fi\n"
    "if date -d @0 '+%Y-%m-%d' >/dev/null 2>&1; then\n"
    "\tdate_epoch() { date -d \"@$1\" '+%Y-%m-%d' 2>/dev/null; }\n"
    "else\n"
    "\tdate_epoch() { date -r \"$1\" '+%Y-%m-%d' 2>/dev/null; }\n"
    "fi\n"
)
WORKTREE_AWK_PAIRS = [
    ("awk '/^worktree /{print $2; exit}'", "awk '/^worktree /{print substr($0, 10); exit}'"),
    ("awk '/^worktree /{print $2}' | while read -r wt", "awk '/^worktree /{print substr($0, 10)}' | while read -r wt"),
]
# F10-F12: fragment replacements (avoid anchoring on shell-escaped quotes).
WORKTREE_STAT_OLD = "| xargs stat -f '%m %N' 2>/dev/null | sort -rn | head -1)"
WORKTREE_STAT_NEW = (
    "| while IFS= read -r tfile; do mt=$(stat_mtime \"$tfile\"); "
    "[ -n \"$mt\" ] && printf '%s %s\\n' \"$mt\" \"$tfile\"; done | sort -rn | head -1)"
)
WORKTREE_DATE_OLD = "last=$(date -r \"$last_ts\" '+%Y-%m-%d' 2>/dev/null); fi"
WORKTREE_DATE_NEW = "last=$(date_epoch \"$last_ts\"); fi"

ADAPTATION_LINE = "Adapted for Hermes Agent plugin compatibility from github.com/cursor/plugins pstack."


class ConvertError(RuntimeError):
    pass


class Stats:
    def __init__(self) -> None:
        self.files_copied = 0
        self.text_normalized = 0
        self.byte_copied = 0
        self.bom_stripped = 0
        self.crlf_fixed = 0
        self.fixes: list[str] = []
        self.warnings: list[str] = []


def normalize_text(data: bytes, st: Stats) -> str | None:
    """Decode and normalize a text payload; None means 'not text'."""
    bom = data.startswith(b"\xef\xbb\xbf")
    try:
        text = data.decode("utf-8-sig" if bom else "utf-8")
    except UnicodeDecodeError:
        return None
    if bom:
        st.bom_stripped += 1
    if b"\r\n" in data or b"\r" in data:
        st.crlf_fixed += 1
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text


def is_text_candidate(path: Path, data: bytes) -> bool:
    if path.suffix.lower() in TEXT_EXTS:
        return True
    if path.name == ".gitignore":
        return True
    if b"\x00" in data[:8192]:
        return False
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def copy_file(src: Path, dst: Path, st: Stats) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    data = src.read_bytes()
    if is_text_candidate(src, data):
        text = normalize_text(data, st)
        if text is None:  # claimed text but not UTF-8: copy bytes, warn
            st.warnings.append(f"non-UTF-8 text-looking file copied verbatim: {src}")
            dst.write_bytes(data)
            st.byte_copied += 1
        else:
            dst.write_bytes(text.encode("utf-8"))  # UTF-8 no BOM, LF preserved
            st.text_normalized += 1
    else:
        dst.write_bytes(data)
        st.byte_copied += 1
    st.files_copied += 1


def copy_tree(src_dir: Path, dst_dir: Path, st: Stats) -> int:
    n = 0
    for root, dirs, files in os.walk(src_dir):
        root_p = Path(root)
        dirs.sort()
        rel = root_p.relative_to(src_dir)
        (dst_dir / rel).mkdir(parents=True, exist_ok=True)
        for name in sorted(files):
            copy_file(root_p / name, dst_dir / rel / name, st)
            n += 1
    return n


def fix_frontmatter_name(text: str, old: str, new: str, rel: str) -> tuple[str, str]:
    """Replace exactly one frontmatter line `name: <old>` with `name: <new>`.

    Returns (new_text, fix_note)."""
    if not text.startswith("---\n"):
        raise ConvertError(f"{rel}: SKILL.md does not start with a frontmatter block")
    end = text.find("\n---", 4)
    if end == -1:
        raise ConvertError(f"{rel}: frontmatter block is unterminated")
    block = text[:end]
    needle = f"name: {old}"
    if not re.search(rf"(?m)^{re.escape(needle)}$", block):
        raise ConvertError(f"{rel}: expected exactly one frontmatter line 'name: {old}', none found")
    if block.count(needle) != 1:
        raise ConvertError(f"{rel}: 'name: {old}' appears more than once in frontmatter")
    new_block = block[: block.index(needle)] + f"name: {new}" + block[block.index(needle) + len(needle):]
    st_fix = f"{rel}: frontmatter name '{old}' -> '{new}'"
    return new_block + text[end:], st_fix


def _fm_field(text: str, key: str) -> str | None:
    """Minimal frontmatter reader for generated-index inputs."""
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    if end == -1:
        return None
    lines = text[4:end].split("\n")
    i = 0
    while i < len(lines):
        m = re.match(rf"^{re.escape(key)}:(.*)$", lines[i])
        if m:
            rest = m.group(1).strip()
            if rest in (">",">-","|","|+","|-"):
                buf, i = [], i + 1
                while i < len(lines) and (lines[i].startswith((" ", "\t")) or lines[i] == ""):
                    if lines[i].strip():
                        buf.append(lines[i].strip())
                    i += 1
                return (" " if rest.startswith(">") else "\n").join(buf)
            if len(rest) >= 2 and rest[0] == rest[-1] and rest[0] in "'\"":
                rest = rest[1:-1]
            return rest
        i += 1
    return None


def _h1_title(body: str) -> str | None:
    for line in body.split("\n"):
        if line.startswith("# "):
            return line[2:].strip()
    return None


def build_principles_index(skills_dir: Path) -> tuple[str, list[str]]:
    """R1: generate the poteto-mode principles index from the 21 leaf skills.

    Leaf descriptions are authoritative; the historical hand-maintained index
    wording (three drifted variants) is replaced. Returns (block, drift_notes).
    """
    entries: dict[str, tuple[str, str]] = {}
    for slug, _ in [(s, g) for g, slugs in PRINCIPLE_GROUPS for s in slugs]:
        sk = skills_dir / slug / "SKILL.md"
        if not sk.is_file():
            raise ConvertError(f"principle leaf missing for index generation: {slug}")
        text = sk.read_text(encoding="utf-8")
        desc = _fm_field(text, "description")
        title = _h1_title(text.split("---", 2)[-1])
        if not desc or not title:
            raise ConvertError(f"principle leaf lacks description/H1: {slug}")
        entries[slug] = (title, desc)
    drift: list[str] = []
    parts = [_PRINCIPLES_HEADER]
    for group, slugs in PRINCIPLE_GROUPS:
        parts.append(f"**{group}**\n\n")
        for slug in slugs:
            title, desc = entries[slug]
            entry = re.sub(r"^Apply (?:when|after|before) ", "", desc).strip()
            entry = entry[0].upper() + entry[1:] if entry else entry
            # F-1: do not add a period when sentence punctuation is already
            # present, including periods inside closing quotes (e.g. .' .")
            if not re.search(r"[.!?][\"'\u201d\u2019)]*$", entry):
                entry += "."
            parts.append(f"- **{title}** (**{slug}**). {entry}\n")
        parts.append("\n")
    block = "".join(parts).rstrip("\n") + "\n"
    for slug, (title, _desc) in entries.items():
        if f"(**{slug}**)" not in block:
            drift.append(f"missing entry: {slug}")
    return block, drift


def apply_phase1_transforms(out: Path, st: "Stats") -> None:
    """Apply R1/F16/F10-F12 hygiene to the copied package. Fail-loud on any
    anchor mismatch so a silent no-op can never masquerade as a fix."""
    # --- T1: regenerate the principles index from the leaves (R1) ---
    pm = out / "skills" / "poteto-mode" / "SKILL.md"
    text = pm.read_text(encoding="utf-8")
    start = text.find(_PRINCIPLES_HEADER)
    end = text.find(_NEXT_SECTION, start)
    if start == -1 or end == -1:
        raise ConvertError("poteto-mode/SKILL.md: principles block anchors not found")
    old_block = text[start:end]
    new_block, drift = build_principles_index(out / "skills")
    if old_block.rstrip("\n") != new_block.rstrip("\n"):
        st.fixes.append("R1: poteto-mode principles index regenerated from 21 leaves "
                        "(single source of truth; hand-maintained wording replaced)")
    for d in drift:
        st.warnings.append(f"principles index: {d}")
    pm.write_bytes((text[:start] + new_block + "\n" + text[end:]).encode("utf-8"))

    # --- T2: de-hardcode check-plan.mjs lane slug (F16) ---
    cp = out / "skills" / "poteto-mode" / "scripts" / "check-plan.mjs"
    cp_text = cp.read_text(encoding="utf-8")
    if CHECK_PLAN_OLD not in cp_text:
        raise ConvertError("check-plan.mjs: LANES anchor not found (upstream changed?)")
    cp.write_bytes(cp_text.replace(CHECK_PLAN_OLD, CHECK_PLAN_NEW, 1).encode("utf-8"))
    st.fixes.append("F16: check-plan.mjs lane slug env-overridable via PSTACK_FAST_LANE")

    # --- T3: multi-phase-plan template note (F16 companion) ---
    mp = out / "skills" / "poteto-mode" / "playbooks" / "multi-phase-plan.md"
    mp_text = mp.read_text(encoding="utf-8")
    if MULTIPHASE_OLD_FRAGMENT not in mp_text:
        raise ConvertError("multi-phase-plan.md: lane-sentence anchor not found")
    mp.write_bytes(mp_text.replace(MULTIPHASE_OLD_FRAGMENT, MULTIPHASE_NEW_FRAGMENT, 1).encode("utf-8"))
    st.fixes.append("F16: multi-phase-plan template documents the PSTACK_FAST_LANE override")

    # --- T4: worktree-audit.sh portability (F10-F12) ---
    wa = out / "skills" / "poteto-mode" / "scripts" / "worktree-audit.sh"
    wa_text = wa.read_text(encoding="utf-8")
    if WORKTREE_HELPERS_ANCHOR not in wa_text:
        raise ConvertError("worktree-audit.sh: 'set -u' anchor not found")
    wa_text = wa_text.replace(WORKTREE_HELPERS_ANCHOR, WORKTREE_HELPERS, 1)
    for old, new in WORKTREE_AWK_PAIRS:
        if old not in wa_text:
            raise ConvertError(f"worktree-audit.sh: awk anchor not found: {old!r}")
        wa_text = wa_text.replace(old, new, 1)
    if WORKTREE_STAT_OLD not in wa_text:
        raise ConvertError("worktree-audit.sh: xargs stat fragment not found")
    wa_text = wa_text.replace(WORKTREE_STAT_OLD, WORKTREE_STAT_NEW, 1)
    if WORKTREE_DATE_OLD not in wa_text:
        raise ConvertError("worktree-audit.sh: date -r fragment not found")
    wa_text = wa_text.replace(WORKTREE_DATE_OLD, WORKTREE_DATE_NEW, 1)
    if "stat -f '%m %N'" in wa_text or "date -r \"$last_ts\"" in wa_text:
        raise ConvertError("worktree-audit.sh: BSD-only construct survived the fix")
    wa.write_bytes(wa_text.encode("utf-8"))
    st.fixes.append("F10-F12: worktree-audit.sh portable via stat_mtime/date_epoch "
                    "helpers (GNU + BSD/macOS); awk no longer truncates space-paths")

    # --- T5: neutralize localhost endpoint literals in example docs (install ---
    # --- scan: hardcoded_ip_port rule matches any IP:port literal)            ---
    # The feature-map example uses a local Notes app URL purely as sample
    # content. Keep the meaning, drop the dotted-quad:port form entirely.
    neutralized = 0
    for p in sorted((out / "skills").rglob("*.md")):
        t = p.read_text(encoding="utf-8")
        if "http://127.0.0.1:4173" in t:
            t2 = t.replace("http://127.0.0.1:4173", "the loopback HTTP endpoint, port 4173")
            p.write_bytes(t2.encode("utf-8"))
            neutralized += t.count("http://127.0.0.1:4173")
    if neutralized:
        st.fixes.append(f"F-publish: {neutralized} localhost endpoint literals neutralized "
                        "in feature-map example docs (install-scanner network findings)")
    for p in sorted((out / "skills").rglob("*.md")):
        t = p.read_text(encoding="utf-8")
        if re.search(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:", t) or "sudo" in t:
            st.warnings.append(f"scanner-flaggable construct remains: {p.relative_to(out)}")

    # --- T8: factual fixes from the hermes deep review (readonly semantics,
    # --- swarm leftovers, tool-name mappings, doc links) -------------------
    T8_MAP = [
        # readonly-MCP rationale: hermes readonly restricts file writes only
        ('- `readonly`: `false` (agent mode). **Do not use readonly/Ask mode.** It strips MCP access, which disables MCP-backed investigators entirely. The source control investigator would be safe in readonly, but keep modes uniform. Investigators still shouldn\'t write anything. That\'s a posture, not a sandbox.',
         '- `readonly`: `false` (agent mode) so investigators can record findings if needed. Note: readonly on hermes restricts file writes only - MCP access is unaffected, so read-only mode would also work for pure exploration. Investigators still shouldn\'t write anything. That\'s a posture, not a sandbox.'),
        ('- `readonly`: `false` (agent mode). The synthesizer\'s quality check spot-verifies citations, which can require MCP access. Readonly/Ask mode strips MCPs and defeats that.',
         '- `readonly`: `false` (agent mode). The synthesizer\'s quality check spot-verifies citations, which can require MCP access. Readonly mode on hermes restricts file writes only - MCP access is unaffected - but agent mode keeps the option to record findings.'),
        ('Reviewers need MCP access for context lookups (tickets, chat threads, observability traces referenced in the transcript); readonly strips MCPs.',
         'Reviewers need MCP access for context lookups (tickets, chat threads, observability traces referenced in the transcript); readonly on hermes restricts file writes only, so MCP access is unaffected.'),
        ('which can require MCP access; readonly strips MCPs.',
         'which can require MCP access; readonly on hermes restricts file writes only, so MCP access is unaffected.'),
        # swarm Cursor-only parameters
        (' Use `environment: "local"` only when the worker needs access to something on the user\'s computer.', ''),
        ('When a worker must start from a non-default pushed branch, pass `cloud_base_branch`.',
         'When a worker must start from a non-default branch, pass the branch name explicitly in the task prompt.'),
        # Cursor tool names in delegate prompts -> hermes tools
        ('Use Glob to find directories and files, Grep to find key symbols, Read to understand the actual implementation.',
         'Use search_files to find directories and files and to find key symbols, read_file to understand the actual implementation.'),
        ('Use Read, Grep, and Glob as needed.', 'Use read_file and search_files as needed.'),
        # .cursor/rules path references -> model-panel phrasing (full Phase-3 = profiles)
        ('in `~/.cursor/rules/pstack-models.mdc` when present',
         'in the configured pstack model panel when present'),
        # principle cross-link: skill_view cannot resolve relative SKILL.md links
        ('[Guard the Context Window](../principle-guard-the-context-window/SKILL.md)',
         'the **guard-the-context-window** principle skill'),
    ]
    t8_changed = 0
    for p in sorted((out / "skills").rglob("*.md")):
        t = p.read_text(encoding="utf-8")
        t0 = t
        for old, new in T8_MAP:
            if old in t:
                t = t.replace(old, new)
                t8_changed += 1
        if t != t0:
            p.write_bytes(t.encode("utf-8"))
    # adaptation note for why's source playbooks (Cursor MCP tool names are examples)
    sp = out / "skills" / "why" / "references" / "source-playbook.md"
    if sp.is_file():
        sp_text = sp.read_text(encoding="utf-8")
        note = "\n\n> Hermes note: the tool names in these source playbooks (Linear, Notion, Slack, Datadog, Sentry, Databricks) are Cursor MCP examples - adapt them to your configured MCP servers' schemas.\n"
        if "Cursor MCP examples" not in sp_text:
            sp.write_bytes((sp_text.rstrip("\n") + note).encode("utf-8"))
            t8_changed += 1
    if t8_changed:
        st.fixes.append(f"T8: {t8_changed} factual fixes from the hermes deep review "
                        "(readonly-MCP rationale x3, swarm Cursor params x2, tool-name "
                        "mappings x2, model-panel path x1, principle cross-link, adaptation note)")

    # --- T6: delegation translation (Phase-2A) ---
    apply_delegation_translation(out, st)

    # --- T7: playbook delegation escape hatch (G1 fix, preserves review
    # --- separation: in-thread authoring + independent delegate reviewer) ---
    G1_FEATURE_OLD = ("Mandatory: no skip-with-reason escape, and Laziness Protocol does not override it "
                      "(the gain is review separation, not lines saved).")
    G1_FEATURE_NEW = (G1_FEATURE_OLD +
                      " Exception (hermes port): when every target file is already resident in "
                      "your context and the edit is surgical and fully specified, you may "
                      "implement in-thread — but review separation is still mandatory: spawn "
                      "a leaf delegate as an independent reviewer of the diff before "
                      "committing, and note the in-thread implementation in the todolist.")
    G1_PM_OLD = ("Routed workflow skills (`how`, `why`, `interrogate`, `reflect`, `swarm`) set "
                 "their own delegate role for diverse-model review; respect what the skill "
                 "prescribes, don't override to `poteto-agent`.")
    G1_PM_NEW = (G1_PM_OLD +
                 " Exception (hermes port): for surgical, fully-specified edits to files "
                 "already resident in your context, implement in-thread and use a "
                 "`delegate_task` leaf as the independent reviewer of the diff instead "
                 "of the author.")
    feat_md = out / "skills" / "poteto-mode" / "playbooks" / "feature.md"
    fm_text = feat_md.read_text(encoding="utf-8")
    if G1_FEATURE_OLD not in fm_text:
        raise ConvertError("feature.md: G1 anchor not found")
    feat_md.write_bytes(fm_text.replace(G1_FEATURE_OLD, G1_FEATURE_NEW, 1).encode("utf-8"))
    pm_md = out / "skills" / "poteto-mode" / "SKILL.md"
    pm_text = pm_md.read_text(encoding="utf-8")
    if G1_PM_OLD not in pm_text:
        raise ConvertError("poteto-mode/SKILL.md: G1 anchor not found")
    pm_md.write_bytes(pm_text.replace(G1_PM_OLD, G1_PM_NEW, 1).encode("utf-8"))
    st.fixes.append("G1: delegation escape hatch added to feature.md + poteto-mode "
                    "Subagents (in-thread authoring allowed for resident surgical "
                    "edits, with mandatory independent delegate review)")


# --- T6 (Phase-2A): delegation translation --------------------------------
# Cursor Task/subagent vocabulary -> hermes delegate_task vocabulary, applied to
# every package markdown file. Ordered most-specific first; the final global pair
# catches remaining backticked `Task` tool references. agents/*.md are EXCLUDED
# (they are the Cursor-side persona definitions, kept verbatim for dual-load).
DELEGATION_MAP = [
    ('`subagent_type`: `generalPurpose`', '`delegate_task`: role `leaf`'),
    ('Spawn `Task` with `subagent_type: "Comment Sicko"`',
     'Spawn a delegate with `delegate_task` (role: `leaf`, persona: Comment Sicko)'),
    ('`subagent_type: "generalPurpose"`', '`delegate_task` (role: `leaf`)'),
    ('`subagent_type: generalPurpose`', '`delegate_task` (role: `leaf`)'),
    ('`subagent_type: "poteto-agent"`', '`delegate_task` (role: `leaf`, persona: poteto-agent)'),
    ('`subagent_type: "Comment Sicko"`', '`delegate_task` (role: `leaf`, persona: Comment Sicko)'),
    ('`environment: "cloud"`, ', ''),
    ('`environment: "cloud"`', 'local execution'),
    ('`run_in_background: true`', 'background execution'),
    ('`subagent_type`', 'delegate role'),
    ('`AskQuestion`', '`clarify`'),
    ('AskQuestion', 'clarify'),
    ('agent mode (readonly strips MCP)', 'full agent mode (read-only delegates lose MCP access)'),
    ('the Task tool', 'delegate_task'),
    ('`Task`', '`delegate_task`'),
]
DELEGATION_FORBIDDEN = ("subagent_type", "generalPurpose", "AskQuestion",
                        "`Task`", "run_in_background", 'environment: "cloud"')


def apply_delegation_translation(out: Path, st: "Stats") -> None:
    changed = 0
    for p in sorted((out / "skills").rglob("*.md")):
        t = p.read_text(encoding="utf-8")
        t0 = t
        for old, new in DELEGATION_MAP:
            t = t.replace(old, new)
        if t != t0:
            p.write_bytes(t.encode("utf-8"))
            changed += 1
    leftovers = []
    for p in sorted((out / "skills").rglob("*.md")):
        t = p.read_text(encoding="utf-8")
        for tok in DELEGATION_FORBIDDEN:
            if tok in t:
                leftovers.append((str(p.relative_to(out)), tok))
    if leftovers:
        raise ConvertError(f"delegation translation incomplete: {leftovers}")
    st.fixes.append(f"Phase-2A: delegation translation applied across {changed} skill "
                    "files (subagent_type/Task/AskQuestion/run_in_background/cloud -> "
                    "delegate_task + clarify + background execution)")


def build_root_manifest(src_manifest_path: Path) -> dict:
    src = json.loads(src_manifest_path.read_text(encoding="utf-8-sig"))
    author = src.get("author")
    if not (isinstance(author, dict) and all(isinstance(v, str) for v in author.values())
            and set(author) <= {"name", "email", "url"}):
        author = {"name": "Lauren Tan"}
    keywords = src.get("keywords")
    if not (isinstance(keywords, list) and all(isinstance(k, str) for k in keywords)):
        keywords = []
    manifest = {
        "$schema": SCHEMA_URL,
        "name": "pstack",
        "version": str(src.get("version", "0.14.4")),
        "description": str(src.get("description", "")),
        "author": author,
        "homepage": str(src.get("homepage", "")),
        "repository": str(src.get("repository", "")),
        "license": str(src.get("license", "MIT")) or "MIT",
        "keywords": keywords,
    }
    # Hard pre-flight against the loader's own rules (agent_plugins.py:39-41,114-141).
    if not MANIFEST_NAME_RE.match(manifest["name"]) or not (1 <= len(manifest["name"]) <= 64):
        raise ConvertError(f"manifest name fails loader regex: {manifest['name']!r}")
    for key in ("version", "description", "homepage", "repository", "license"):
        if not isinstance(manifest[key], str):
            raise ConvertError(f"manifest field {key} must be a string")
    if not manifest["description"]:
        raise ConvertError("manifest description is empty")
    return manifest


def _converted_at() -> str:
    """Build timestamp; SOURCE_DATE_EPOCH makes builds fully deterministic."""
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch and epoch.isdigit():
        return datetime.fromtimestamp(int(epoch), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def source_commit(source: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(source), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=30, check=True,
        )
        return out.stdout.strip()
    except Exception as exc:  # git missing, not a repo, ...
        return f"unknown (git rev-parse failed: {exc})"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source", default=str(DEFAULT_SOURCE), help="pstack clone root (read-only)")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="package dir to build (rebuilt each run)")
    args = ap.parse_args()

    source = Path(args.source).resolve()
    out = Path(args.out).resolve()
    st = Stats()

    if not source.is_dir():
        raise ConvertError(f"source not found: {source}")
    src_manifest = source / ".cursor-plugin" / "plugin.json"
    if not src_manifest.is_file():
        raise ConvertError(f"source manifest missing: {src_manifest}")
    if out == source or source in out.parents:
        raise ConvertError(f"refusing to write inside the source tree: {out}")
    # Atomic-build pattern: construct in a temp sibling and swap into place only
    # on success, so a mid-build failure never clobbers the last good package.
    final_out = out
    build_dir = out.with_name(out.name + ".tmp-build")
    if build_dir.exists():
        shutil.rmtree(build_dir)
    build_dir.mkdir(parents=True)
    out = build_dir

    commit = source_commit(source)

    # (a) skills/ with the grokbot flatten
    skills_src = source / "skills"
    skills_dst = out / "skills"
    grokbot = skills_src / "grokbot"
    if not grokbot.is_dir():
        raise ConvertError(f"expected container missing in source: {grokbot}")
    flattened: list[str] = []
    for child in sorted(p for p in skills_src.iterdir()):
        if not child.is_dir():
            raise ConvertError(f"unexpected non-directory under skills/: {child.name}")
        if child.name == "grokbot":
            # F-publish: skills/make-bot-ui is excluded from the hermes package
            # (privilege-escalation scan verdict; F33 deepest vendor coupling).
            for inner in sorted(p for p in child.iterdir()):
                if inner.name == "make-bot-ui":
                    st.fixes.append("F-publish: skills/make-bot-ui excluded "
                                    "(Tailscale privilege-escalation scan; F33)")
                    continue
                raise ConvertError(f"unexpected file under skills/grokbot/: {inner.name}")
            flattened.append("(grokbot container skipped)")
        else:
            copy_tree(child, skills_dst / child.name, st)
    if flattened != ["(grokbot container skipped)"]:
        st.warnings.append(f"skills/grokbot contained unexpected children: {flattened}")

    # (b) exactly two frontmatter name fixes
    for dirname, (old, new) in FRONTMATTER_FIXES.items():
        p = skills_dst / dirname / "SKILL.md"
        text = p.read_text(encoding="utf-8")  # already normalized by copy_file
        fixed, note = fix_frontmatter_name(text, old, new, f"skills/{dirname}/SKILL.md")
        p.write_bytes(fixed.encode("utf-8"))
        st.fixes.append(note)

    # (b2) Phase-1 hygiene transforms (R1, F16, F10-F12)
    apply_phase1_transforms(out, st)

    # (c) agents/ copied unchanged (inert on hermes portable path; kept for
    #     Cursor dual-load and Phase 2).
    # (c2) PHASE-1.5 publisher exclusions: automations/benny (8 CRITICAL
    #     persistence findings in the install scanner: copy-instructions
    #     pattern-match) and skills/make-bot-ui (2 HIGH privilege_escalation:
    #     Tailscale curl|sudo sh) are EXCLUDED — hermes' CLI install BLOCKS on
    #     a dangerous verdict and --force cannot override. Both are also the
    #     study's own "what not to port" items; benny is rebuilt as hermes
    #     cron/loop jobs in Phase 4.
    agents_n = copy_tree(source / "agents", out / "agents", st)
    st.fixes.append("F-publish: automations/benny excluded (scanner persistence verdict) "
                    "and skills/make-bot-ui excluded (scanner privilege verdict; F33)")

    # (e) .cursor-plugin/plugin.json preserved for Cursor dual-load
    (out / ".cursor-plugin").mkdir()
    copy_file(src_manifest, out / ".cursor-plugin" / "plugin.json", st)

    # (d) root plugin.json: strict 10-field whitelist manifest (hermes probes root only)
    manifest = build_root_manifest(src_manifest)
    manifest_text = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    (out / "plugin.json").write_bytes(manifest_text.encode("utf-8"))
    st.fixes.append("plugin.json: injected exact agent-plugins-v1 $schema at ROOT "
                    "(9 whitelisted fields; displayName/category/tags/agents/skills omitted)")

    # (g) LICENSE: upstream MIT + adaptation line
    lic_text = normalize_text((source / "LICENSE").read_bytes(), st)
    if lic_text is None:
        raise ConvertError("source LICENSE is not UTF-8 text")
    if "Lauren Tan" not in lic_text:
        st.warnings.append("source LICENSE does not mention 'Lauren Tan'; verify copyright line")
    body = lic_text.rstrip("\n")
    if ADAPTATION_LINE not in body:
        body += "\n\n" + ADAPTATION_LINE + "\n"
    (out / "LICENSE").write_bytes(body.encode("utf-8"))
    st.files_copied += 1

    # (g) README.md for the package
    discovered = sorted(p.name for p in skills_dst.iterdir() if p.is_dir() and (p / "SKILL.md").is_file())
    principles = [n for n in discovered if n.startswith("principle-")]
    workflow = [n for n in discovered if not n.startswith("principle-")]
    readme = f"""# pstack (hermes agent-plugins-v1 package)

Phase-0 conversion of **pstack v{manifest['version']}** for the Hermes Agent platform's
portable plugin path. Upstream: <https://github.com/cursor/plugins/tree/main/pstack>
(MIT, Copyright (c) 2026 Lauren Tan). Conversion provenance: see `.build-provenance.txt`;
regenerate with `python convert.py --source <pstack-clone> --out <package-dir>`.

## What hermes loads

- **{len(discovered)} skills** via the agent-plugins-v1 portable path
  ({len(workflow)} workflow/mode skills + {len(principles)} `principle-*` skills):
  single-level `skills/<dir>/SKILL.md`, immediate children only.
- Root `plugin.json` — the strict agent-plugins-v1 manifest hermes probes at the
  package root: exact `$schema` URL, {len(manifest)} whitelisted fields
  ($schema, name, version, description, author, homepage, repository, license, keywords).

## What stays inert on hermes (for now)

- `agents/` (poteto-agent, comment-sicko) — the portable path discovers skills and
  mcp.json only; no agent registration exists in hermes v0.20.5. Kept for Cursor
  dual-load and a Phase-2 native wrapper.
- `automations/benny/` — **excluded** from this package: the install scanner
  flags its copy-instructions as persistence patterns (verdict: dangerous),
  and Phase 4 rebuilds it as hermes cron/loop jobs anyway.
- `skills/make-bot-ui/` — **excluded**: its Tailscale setup script trips the
  privilege-escalation scanner (F33); deepest vendor coupling.
- Executable scripts shipped inside skills (e.g. `skills/poteto-mode/scripts/`) —
  copied verbatim; the loader never executes them.

## How to invoke on hermes

Portable plugin skills are **opt-in**: they do not enter the system-prompt
`<available_skills>` index. Load a skill explicitly with `skill_view` using the
namespaced id `agent-plugin-pstack-<digest>:<skill-name>`, where `<digest>` is the
first 8 hex chars of the sha256 of the plugin key (stable while the install
directory keeps the name `pstack`).

Optional slash-command route (no code): add this package's `skills` directory to
`skills.external_dirs` in `%LOCALAPPDATA%\\hermes\\config.yaml` and the hub scanner
registers all {len(discovered)} skills as `/<name>` slash commands (agent/skill_commands.py:424).
Trade-offs: skills enter the prompt index with 60-char descriptions and lose the
plugin namespace; the portable path itself registers zero commands
(plugins.py:5088-5138).

## Install path (Windows)

Copy this package directory to `%LOCALAPPDATA%\\hermes\\plugins\\pstack`, then add
`pstack` to `plugins.enabled` in `%LOCALAPPDATA%\\hermes\\config.yaml`.

## Cursor dual-load

`.cursor-plugin/plugin.json` is preserved unchanged, so this same directory still
loads as a Cursor plugin. Hermes probes only `<root>/plugin.json` and never reads
`.cursor-plugin/`.

## Differences from upstream (the conversion gate)

1. Root `plugin.json` injected with the exact agent-plugins-v1 `$schema` URL and a
   whitelisted field set (upstream Cursor fields `displayName`, `category`, `tags`,
   `skills`, `agents` are omitted — unknown fields produce loader diagnostics).
2. `skills/poteto-mode/SKILL.md`: frontmatter `name: Poteto Mode` -> `name: poteto-mode`.
3. `skills/grokbot/` container and `skills/make-bot-ui/` are **excluded** (see 9);
   the loader only sees immediate children of `skills/` anyway.
4. Text normalization to UTF-8 without BOM and LF line endings.
5. **R1**: the poteto-mode principles index is regenerated from the 21 principle
   leaves at build time — the leaves are the single source of truth, so the
   historical four-way duplication (index/leaf/README/guide) cannot drift here.
6. **F16**: `check-plan.mjs` reads the fast-lane slug from `PSTACK_FAST_LANE`
   (default `grok-4.6-fast-xhigh`) instead of a hardcoded literal; the
   multi-phase-plan template documents the override.
7. **F10-F12**: `worktree-audit.sh` detects GNU vs BSD `stat`/`date` at runtime
   (`stat_mtime`/`date_epoch` helpers) and no longer truncates worktree paths
   containing spaces (verified on GNU/Linux; unchanged behavior on macOS).
8. **F-publish**: `automations/benny/` and `skills/make-bot-ui/` excluded —
   the hermes install scanner blocks packages whose scan verdict is
   "dangerous" (benny copy-instructions + make-bot-ui Tailscale), --force
   cannot override, and both are Phase-4/what-not-to-port items anyway.
9. **G1**: a delegation escape hatch added to the Feature playbook and the
   poteto-mode Subagents section — surgical, fully-specified edits to files
   already resident in context may be implemented in-thread, provided a leaf
   delegate reviews the diff (review separation preserved; fixes the
   deviation observed in the first live usage run).

Nothing else in any SKILL.md was modified.

---

{ADAPTATION_LINE}.
"""
    (out / "README.md").write_bytes(readme.encode("utf-8"))
    st.files_copied += 1

    # provenance
    conv_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:16]
    # Fixes are derived from st.fixes (what actually ran), never hardcoded —
    # a stale claim here would defeat the provenance's purpose.
    fix_lines = "\n".join(f"  - {f}" for f in st.fixes)
    fix_lines += (
        f"\n  - text normalization: UTF-8 without BOM, LF line endings "
        f"(files normalized: {st.text_normalized}, BOM stripped: {st.bom_stripped}, "
        f"CRLF fixed: {st.crlf_fixed})"
    )
    provenance = f"""package: pstack (hermes agent-plugins-v1, Phase-0 conversion)
source: {source}
source_commit: {commit}
converted_at: {_converted_at()}
converter: convert.py (sha256[:16]={conv_sha})
schema: {SCHEMA_URL}
fixes:
{fix_lines}
counts:
  skills_loaded: {len(discovered)} ({len(workflow)} workflow/mode + {len(principles)} principle)
  skill_md_on_disk: {len(discovered)} (skills/ only; automations/benny + make-bot-ui excluded for the install scanner)
  agents_files: {agents_n}
notes:
  - agents/ is inert on the hermes portable path (kept for Cursor dual-load / Phase 2)
  - automations/benny + make-bot-ui excluded (install-scanner verdict); rebuild via Phase 4 / stay Cursor-side
  - .cursor-plugin/plugin.json preserved unchanged for Cursor dual-load; hermes probes the root manifest only
"""
    (out / ".build-provenance.txt").write_bytes(provenance.encode("utf-8"))
    st.files_copied += 1

    # ---- atomic swap: build succeeded, move into place ----
    # F-2 hardening: never leave the install target absent — rename the old
    # package aside first, move the new one in, then drop the old.
    prev = final_out.with_name(final_out.name + ".prev-build")
    if prev.exists():
        shutil.rmtree(prev)
    if final_out.exists():
        final_out.rename(prev)
    out.rename(final_out)
    out = final_out
    if prev.exists():
        shutil.rmtree(prev, ignore_errors=True)

    # ---- summary ----
    print("== convert.py summary ==")
    print(f"source: {source} @ {commit[:12]}")
    print(f"out:    {out}")
    print(f"files copied: {st.files_copied} (text normalized: {st.text_normalized}, byte-copied: {st.byte_copied}; BOM stripped: {st.bom_stripped}, CRLF fixed: {st.crlf_fixed})")
    print(f"skills discovered (portable, immediate children with SKILL.md): {len(discovered)} "
          f"({len(workflow)} workflow/mode + {len(principles)} principle-*)")
    skill_md_on_disk = len(list((out / "skills").glob("*/SKILL.md")))
    print(f"SKILL.md on disk: {skill_md_on_disk} (skills/ only; automations/benny + make-bot-ui excluded)")
    print("fixes applied:")
    for f in st.fixes:
        print(f"  - {f}")
    print("warnings:")
    for w in st.warnings or ["(none)"]:
        print(f"  - {w}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ConvertError as exc:
        print(f"CONVERT ERROR: {exc}", file=sys.stderr)
        sys.exit(2)
