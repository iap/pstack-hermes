#!/usr/bin/env python3
"""Docs drift gate for the hand-written instructions.

The package is hand-written source, so `validate.py` keeps it honest. The
*docs* have no such gate, and they have already drifted once: the root-layout
migration left `AGENTS.md` and `CONTRIBUTING.md` describing a `pstack/`
subdirectory that no longer exists. This tool checks the facts that actually
broke:

1. Router links in `AGENTS.md` / `docs/agent/README.md` resolve.
2. `docs/agent/layout.md` and `.gitattributes` agree in both directions:
   generated/copied rows must be marked generated, hand-written rows must
   not be, and every generated marker must appear in layout.md.
3. Hand-written docs (plus `README.md`) carry no stale
   package-subdirectory paths (`pstack/skills/`, `pstack/config/`,
   `$PWD/pstack`, ...).
4. `release.yml` packages only paths that exist in the tree (the dropped
   `after-install.md` would have failed every release).
5. Install docs (`README.md`, `docs/USING.md`) do not resurrect the dead
   `master` subdirectory install route.
6. Shipped playbooks resolve the trunk at runtime instead of hardcoding
   `origin/master` or `origin/main`.

Exit codes: 0 clean; 1 drift found; 2 unreadable input.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]

ROUTER_DOCS = ("AGENTS.md", "docs/agent/README.md")
HAND_WRITTEN_DOCS = (
    "AGENTS.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    ".github/PULL_REQUEST_TEMPLATE.md",
)
HAND_WRITTEN_DOC_GLOBS = ("docs/*.md", "docs/agent/*.md")
# README.md is generated, but its install prose is user-facing and drifted once
# with the root-layout migration; scan it for the same stale package paths.
SCAN_EXTRA_DOCS = ("README.md",)
INSTALL_ROUTE_DOCS = ("README.md", "docs/USING.md")

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
PATH_CELL_RE = re.compile(r"^\|\s*(?P<paths>(?:`[^`]+`[,\s]*)+)\|\s*(?P<kind>[^|]+?)\s*\|")
BACKTICK_PATH_RE = re.compile(r"`([^`]+)`")
WORKFLOW_TOKEN_RE = re.compile(r"`([A-Za-z0-9_.-]+\.ya?ml)`")
STALE_PATH_RE = re.compile(
    r"(?<![\w./-])pstack/(?:skills|config|assets|agents|docs|patches)/"
    r"|pstack/(?:plugin\.json|README\.md|\.gitattributes)"
    r"|pstack/\.build-provenance"
    r"|\$PWD/pstack"
    r"|pwd\)/pstack"
)
GENERATED_KINDS = frozenset({"generated", "copied"})
HAND_WRITTEN_KINDS = frozenset({"hand-written"})
STALE_INSTALL_RE = re.compile(
    r"`?master`?\s+subdirectory\s+installs?"
    r"|subdirectory\s+installs?\s+are\s+re-cloned"
    r"|Subdirectory\s+updates\s+replace\s+shipped\s+skills",
    re.IGNORECASE,
)
HARDCODED_TRUNK_RE = re.compile(
    r"\b[A-Za-z0-9][A-Za-z0-9_.-]*/(?:master|main)\b"
    r"|\b(?:branch|branches|worktree|reset)\b[^.\n]{0,40}`(?:[A-Za-z0-9][A-Za-z0-9_.-]*/)?(?:master|main)`"
)
GIT_COMMAND_TRUNK_RE = re.compile(
    r"\bgit (?:reset --hard|worktree add|checkout|switch|branch|rebase|merge)"
    r"[^`\n;&|]*(?<![\w/$/-])(?:master|main)\b"
    r"|\bgit show [^`\n;&|]*(?<![\w/$/-])(?:master|main):"
)
LEGACY_REPO = "iap/pstack-hermes"
LEGACY_PREFIX_TERMINATORS = " \t\r\n/`'\"(=:"
LEGACY_TOKEN_BOUNDARIES = " \t\r\n`'\"(=<>[]{};,!#|*_~"
LEGACY_NAME_CONTINUATIONS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-."
)
BARE_PACKAGE_RE = re.compile(r"(?<![\w./-])pstack/(?=\s|$|`)")
CONTRACT_DOCS = frozenset({"AGENTS.md", "CONTRIBUTING.md"})
LAYOUT_GENERATED_EXEMPT = frozenset({"plugin.yaml"})
ZIP_SOURCE_RE = re.compile(r'zip -r pstack-"\$\{TAG_NAME\}"\.zip (?P<paths>[^;]+)')


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _github_repo_prefix(text: str, pos: int) -> bool:
    start = pos
    while start > 0 and text[start - 1] not in LEGACY_TOKEN_BOUNDARIES:
        start -= 1
    token = text[start:pos].lower()
    if token.endswith(":"):
        return token[:-1].rsplit("@", 1)[-1] == "github.com"
    if "://" in token:
        parsed = urlparse(token)
        return (parsed.hostname or "") == "github.com" and parsed.path == "/"
    return token == "github.com/"


def _subdir_token_ends(rest: str) -> bool:
    if not rest:
        return True
    if rest[0] != ".":
        return rest[0] not in LEGACY_NAME_CONTINUATIONS
    return len(rest) == 1 or rest[1] not in LEGACY_NAME_CONTINUATIONS


def _legacy_target(text: str, pos: int) -> bool:
    """True when the repo name at *pos* points at the removed `pstack/` subdir."""
    if pos > 0:
        separator = text[pos - 1]
        if separator not in LEGACY_PREFIX_TERMINATORS:
            return False
        if separator in "/:" and not _github_repo_prefix(text, pos):
            return False
    tail = text[pos + len(LEGACY_REPO) :].lower()
    if tail.startswith(".git"):
        tail = tail[4:]
    if tail.startswith("/tree/"):
        _, sep, subdir = tail[len("/tree/") :].partition("/")
        if not sep or not subdir.startswith("pstack"):
            return False
        return _subdir_token_ends(subdir[len("pstack") :])
    if not (tail.startswith("/pstack") or tail.startswith("#pstack")):
        return False
    return _subdir_token_ends(tail[7:])


def _doc_paths(root: Path) -> list[Path]:
    paths = [root / rel for rel in (*HAND_WRITTEN_DOCS, *SCAN_EXTRA_DOCS)]
    for pattern in HAND_WRITTEN_DOC_GLOBS:
        paths.extend(sorted(root.glob(pattern)))
    seen: dict[Path, None] = {}
    for path in paths:
        seen.setdefault(path, None)
    return list(seen)


def check_router_links(root: Path = ROOT) -> list[str]:
    problems: list[str] = []
    for rel in ROUTER_DOCS:
        doc = root / rel
        if not doc.is_file():
            problems.append(f"{rel}: missing router doc")
            continue
        for target in LINK_RE.findall(_read(doc)):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            resolved = (doc.parent / target.split("#", 1)[0]).resolve()
            if not resolved.exists():
                problems.append(f"{rel}: broken link target {target}")
    return problems


def _gitattributes_generated(root: Path) -> set[str]:
    attrs = root / ".gitattributes"
    if not attrs.is_file():
        raise FileNotFoundError(attrs)
    markers: set[str] = set()
    for line in _read(attrs).splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or "linguist-generated=true" not in line:
            continue
        path = line.split()[0]
        markers.add(path[:-2] if path.endswith("/**") else path)
    return markers


def _covers(marker: str, path: str) -> bool:
    bare = path.rstrip("/")
    if marker.endswith("/"):
        return bare == marker.rstrip("/") or bare.startswith(marker)
    return bare == marker


def check_layout_manifest(root: Path = ROOT) -> list[str]:
    layout = root / "docs" / "agent" / "layout.md"
    if not layout.is_file():
        return ["docs/agent/layout.md: missing layout doc"]
    try:
        markers = _gitattributes_generated(root)
    except FileNotFoundError:
        return [".gitattributes: missing (cannot cross-check generated paths)"]

    problems: list[str] = []
    documented: list[str] = []
    for line in _read(layout).splitlines():
        match = PATH_CELL_RE.match(line)
        if not match:
            continue
        kind = match.group("kind").strip().lower()
        for path in BACKTICK_PATH_RE.findall(match.group("paths")):
            generated = any(_covers(marker, path) for marker in markers)
            if kind in GENERATED_KINDS:
                documented.append(path)
            if kind in GENERATED_KINDS and not generated:
                problems.append(
                    f"docs/agent/layout.md: {path} listed {kind} but .gitattributes does not mark it generated"
                )
            if kind in HAND_WRITTEN_KINDS and generated:
                problems.append(
                    f"docs/agent/layout.md: {path} listed hand-written but .gitattributes marks it generated"
                )
    for marker in sorted(
        m for m in markers if m.rstrip("/") not in LAYOUT_GENERATED_EXEMPT
    ):
        bare = marker.rstrip("/")
        if not any(
            path.rstrip("/") == bare or path.rstrip("/").startswith(f"{bare}/")
            for path in documented
        ):
            problems.append(
                f"docs/agent/layout.md: .gitattributes marks {marker} generated but layout.md does not list it"
            )
    return problems


def check_stale_paths(root: Path = ROOT) -> list[str]:
    problems: list[str] = []
    for doc in _doc_paths(root):
        if not doc.is_file():
            continue
        rel = doc.relative_to(root).as_posix()
        for lineno, line in enumerate(_read(doc).splitlines(), start=1):
            if STALE_PATH_RE.search(line):
                problems.append(f"{rel}:{lineno}: stale package subdirectory path: {line.strip()}")
            elif rel in CONTRACT_DOCS and BARE_PACKAGE_RE.search(line):
                problems.append(f"{rel}:{lineno}: stale bare pstack/ package path: {line.strip()}")
    template = root / ".github" / "PULL_REQUEST_TEMPLATE.md"
    if template.is_file():
        for lineno, line in enumerate(_read(template).splitlines(), start=1):
            if "pstack/" in line:
                problems.append(
                    f".github/PULL_REQUEST_TEMPLATE.md:{lineno}: stale pstack/ path: {line.strip()}"
                )
    return problems


def check_stale_install_route(root: Path = ROOT) -> list[str]:
    problems: list[str] = []
    for rel in INSTALL_ROUTE_DOCS:
        doc = root / rel
        if not doc.is_file():
            continue
        text = _read(doc)
        for match in STALE_INSTALL_RE.finditer(text):
            lineno = text.count("\n", 0, match.start()) + 1
            snippet = " ".join(match.group(0).split())
            problems.append(
                f"{rel}:{lineno}: stale subdirectory-install route: {snippet}"
            )
        lower = text.lower()
        start = 0
        while True:
            pos = lower.find(LEGACY_REPO, start)
            if pos == -1:
                break
            if _legacy_target(text, pos):
                lineno = text.count("\n", 0, pos) + 1
                line_end = text.find("\n", pos)
                snippet = " ".join(
                    text[pos : line_end if line_end != -1 else len(text)].split()
                )
                problems.append(
                    f"{rel}:{lineno}: stale subdirectory-install route: {snippet}"
                )
            start = pos + len(LEGACY_REPO)
    return problems


def check_portable_trunk_refs(root: Path = ROOT) -> list[str]:
    problems: list[str] = []
    for playbook in sorted((root / "skills").glob("*/playbooks/*.md")):
        text = _read(playbook)
        for pattern in (HARDCODED_TRUNK_RE, GIT_COMMAND_TRUNK_RE):
            for match in pattern.finditer(text):
                lineno = text.count("\n", 0, match.start()) + 1
                snippet = " ".join(match.group(0).split())
                problems.append(
                    f"{playbook.relative_to(root)}:{lineno}: hardcoded trunk ref: {snippet}; "
                    "use origin/HEAD or the forge default"
                )
    return problems


def check_release_sources(root: Path = ROOT) -> list[str]:
    workflow = root / ".github" / "workflows" / "release.yml"
    if not workflow.is_file():
        return [".github/workflows/release.yml: missing release workflow"]
    problems: list[str] = []
    matches = list(ZIP_SOURCE_RE.finditer(_read(workflow)))
    if not matches:
        # A refactored zip line must fail loudly: a check that finds nothing to
        # check would otherwise report clean forever.
        return ["release.yml: no zip invocation found; the packaging check cannot run"]
    for match in matches:
        for token in match.group("paths").split():
            token = token.strip().rstrip("/")
            if not token or "$" in token or token == "assets":
                # assets/ is packaged only when present; the fallback zip drops it.
                continue
            if not (root / token).exists():
                problems.append(f"release.yml: packaged path does not exist: {token}")
    return problems


MODEL_PANEL = Path("tools") / "assets" / "model-panel.json"
MODELS_DOC = Path("docs") / "MODELS.md"


def check_model_map(root: Path = ROOT) -> list[str]:
    """The shipped-panel table in docs/MODELS.md must equal the panel JSON.

    A stale table is how #216 read: the panel moved, the docs still named the
    old slug, and only the live catalog check caught it.
    """
    panel_path, doc_path = root / MODEL_PANEL, root / MODELS_DOC
    if not panel_path.is_file():
        return [f"{MODEL_PANEL}: missing"]
    if not doc_path.is_file():
        return [f"{MODELS_DOC}: missing"]
    roles = json.loads(_read(panel_path)).get("roles", {})
    if not isinstance(roles, dict) or not roles:
        return [f"{MODEL_PANEL}: no roles"]

    text = _read(doc_path)
    if "## The shipped panel" not in text:
        return [f"{MODELS_DOC}: '## The shipped panel' section missing"]
    section = text.split("## The shipped panel", 1)[1].split("\n## ", 1)[0]
    documented: dict[str, set[str]] = {}
    problems: list[str] = []
    for line in section.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != 2 or cells[0] in {"Role", "---"}:
            continue
        if cells[0] in documented:
            # A second row for the same role would overwrite the first and could
            # hide a stale slug behind a correct duplicate.
            problems.append(f"{MODELS_DOC}: duplicate row for role {cells[0]!r}")
            continue
        documented[cells[0]] = set(re.findall(r"`([^`]+)`", cells[1]))

    for role, value in roles.items():
        expected = {value} if isinstance(value, str) else set(value)
        if role not in documented:
            problems.append(f"{MODELS_DOC}: role missing from shipped panel: {role}")
        elif documented[role] != expected:
            problems.append(
                f"{MODELS_DOC}: role {role!r} lists {sorted(documented[role])}, panel has {sorted(expected)}"
            )
    for role in sorted(set(documented) - set(roles)):
        problems.append(f"{MODELS_DOC}: documents a role the panel does not define: {role}")
    return problems


VOCAB_DOC = Path("docs") / "hermes-vocabulary.md"
VOCAB_SKILL = Path("skills") / "hermes-vocabulary" / "SKILL.md"
VOCAB_BANS = Path("tools") / "bans.py"
VOCAB_VALIDATE = Path("tools") / "validate.py"
VOCAB_BEGIN = "<!-- VOCAB-MAP-BEGIN -->"
VOCAB_END = "<!-- VOCAB-MAP-END -->"
VOCAB_GATE_SOURCES = {
    "tools/bans.py:DELEGATION_VOCAB_BANS": ("DELEGATION_VOCAB_BANS", VOCAB_BANS, True),
    "tools/bans.py:TRANSCRIPT_VOCAB_BANS": ("TRANSCRIPT_VOCAB_BANS", VOCAB_BANS, True),
    "tools/validate.py:HERMES_ADAPTATION_BANS": ("HERMES_ADAPTATION_BANS", VOCAB_VALIDATE, True),
    "tools/validate.py:check_phase1:t9_toks": ("t9_toks", VOCAB_VALIDATE, False),
}
VOCAB_GATE_SCOPES = {"t9_toks": "check_phase1"}
VOCAB_AUGMENTED = "<augmented>"


def _vocab_literals(
    sources: dict[Path, str],
) -> dict[Path, dict[str, list[str] | dict[str, str] | str]]:
    names = {spec[0] for spec in VOCAB_GATE_SOURCES.values()}
    found: dict[Path, dict[str, list[str] | dict[str, str] | str]] = {}
    for path, source in sources.items():
        tree = ast.parse(source)
        per_file: dict[str, list[str] | dict[str, str] | str] = {}
        def augmented_names(nodes: list[ast.stmt], allowed: set[str]) -> set[str]:
            return {
                child.target.id
                for node in nodes
                for child in ast.walk(node)
                if isinstance(child, ast.AugAssign)
                and isinstance(child.target, ast.Name)
                and child.target.id in allowed
            }

        augmented = augmented_names(
            [
                node
                for node in tree.body
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            ],
            names - set(VOCAB_GATE_SCOPES),
        )
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name in VOCAB_GATE_SCOPES.values():
                scoped = {name for name, func in VOCAB_GATE_SCOPES.items() if func == node.name}
                augmented |= augmented_names(node.body, scoped)

        def capture(
            node: ast.AST,
            allowed: set[str],
            *,
            augmented: set[str] = augmented,
            per_file: dict[str, list[str] | dict[str, str] | str] = per_file,
        ) -> None:
            targets = node.targets if isinstance(node, ast.Assign) else (
                [node.target] if isinstance(node, ast.AnnAssign) else []
            )
            for target in targets:
                if not isinstance(target, ast.Name) or target.id not in allowed:
                    continue
                if target.id in augmented:
                    per_file[target.id] = VOCAB_AUGMENTED
                    continue
                try:
                    value = ast.literal_eval(node.value)
                except (ValueError, TypeError):
                    continue
                if isinstance(value, (list, tuple, dict)):
                    per_file[target.id] = value

        for node in tree.body:
            capture(node, names - set(VOCAB_GATE_SCOPES))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef) or node.name not in VOCAB_GATE_SCOPES.values():
                continue
            scoped = {name for name, func in VOCAB_GATE_SCOPES.items() if func == node.name}
            for child in ast.walk(node):
                capture(child, scoped)
        found[path] = per_file
    return found


def _vocab_table_rows(text: str) -> list[str]:
    rows: list[str] = []
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if not cells or cells[0] in {"---", ""} or cells[0].startswith("Use this"):
            continue
        rows.append(cells[0])
    return rows


def check_vocab_map(root: Path = ROOT) -> list[str]:
    """docs/hermes-vocabulary.md owns the mapping; gate lists must agree with it."""
    problems: list[str] = []
    for path in (VOCAB_DOC, VOCAB_SKILL, VOCAB_BANS, VOCAB_VALIDATE):
        if not (root / path).is_file():
            problems.append(f"{path}: missing")
    if problems:
        return problems

    doc_text = _read(root / VOCAB_DOC)
    if VOCAB_BEGIN not in doc_text or VOCAB_END not in doc_text:
        return [f"{VOCAB_DOC}: machine-readable VOCAB-MAP block missing"]
    block = doc_text.split(VOCAB_BEGIN, 1)[1].split(VOCAB_END, 1)[0]
    match = re.search(r"```json\s*(.*?)\s*```", block, re.S)
    if not match:
        return [f"{VOCAB_DOC}: VOCAB-MAP block has no json fence"]
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        return [f"{VOCAB_DOC}: invalid VOCAB-MAP json: {exc}"]
    gates = data.get("gates")
    if not isinstance(gates, dict):
        return [f"{VOCAB_DOC}: VOCAB-MAP has no gates object"]

    for key in sorted(set(gates) - set(VOCAB_GATE_SOURCES)):
        problems.append(
            f"{VOCAB_DOC}: gates.{key} has no checker coverage "
            f"(add it to VOCAB_GATE_SOURCES in tools/check_docs.py)"
        )
    literals = _vocab_literals(
        {VOCAB_BANS: _read(root / VOCAB_BANS), VOCAB_VALIDATE: _read(root / VOCAB_VALIDATE)}
    )
    for key, (name, path, exact) in VOCAB_GATE_SOURCES.items():
        documented = gates.get(key)
        if documented is None:
            problems.append(f"{VOCAB_DOC}: gates.{key} missing (enforced in {path})")
            continue
        if name not in literals.get(path, {}):
            problems.append(f"{path}: {name} missing (canonical: {VOCAB_DOC})")
            continue
        value = literals[path][name]
        if value == VOCAB_AUGMENTED:
            problems.append(
                f"{path}: {name} uses an augmented assignment; the literal gate cannot verify it"
            )
            continue
        code = set(value)
        documented_set = set(documented)
        for token in sorted(documented_set - code):
            problems.append(f"{path}: {name} missing {token!r} (canonical: {VOCAB_DOC})")
        if exact:
            for token in sorted(code - documented_set):
                problems.append(
                    f"{VOCAB_DOC}: gates.{key} missing enforced token {token!r} (update {VOCAB_DOC})"
                )

    doc_rows = _vocab_table_rows(doc_text.split("## Canonical mapping", 1)[-1].split("## ", 1)[0])
    skill_rows = _vocab_table_rows(_read(root / VOCAB_SKILL))
    for index in range(max(len(doc_rows), len(skill_rows))):
        expected = doc_rows[index] if index < len(doc_rows) else "<missing>"
        actual = skill_rows[index] if index < len(skill_rows) else "<missing>"
        if expected != actual:
            problems.append(
                f"{VOCAB_SKILL}: row {index + 1} is {actual!r}, canonical is {expected!r} "
                f"(update {VOCAB_SKILL})"
            )
    return problems


CHECKS = (
    ("router links resolve", check_router_links),
    ("layout matches .gitattributes", check_layout_manifest),
    ("no stale package subdirectory paths", check_stale_paths),
    ("no stale subdirectory-install route", check_stale_install_route),
    ("shipped playbooks avoid hardcoded trunk refs", check_portable_trunk_refs),
    ("release packaging sources exist", check_release_sources),
    ("model panel matches docs/MODELS.md", check_model_map),
    ("vocabulary map matches gate lists and skill", check_vocab_map),
)


def check(root: Path = ROOT) -> tuple[int, list[str]]:
    lines: list[str] = [f"== check_docs.py ==\nroot: {root}"]
    problems: list[str] = []
    for label, fn in CHECKS:
        found = fn(root)
        if found:
            lines.append(f"  FAIL  {label}")
            lines.extend(f"        {item}" for item in found)
            problems.extend(found)
        else:
            lines.append(f"  PASS  {label}")
    lines.append("")
    lines.append("verdict: " + ("PASS" if not problems else f"FAIL ({len(problems)} problem(s))"))
    return (0 if not problems else 1), lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=str(ROOT), help="repository root (default: this repo)")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"error: not a directory: {root}", file=sys.stderr)
        return 2
    code, lines = check(root)
    print("\n".join(lines))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
