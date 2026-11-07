"""Poteto-mode principles index generation (extracted from tools/convert.py).

Standalone home for the R1 index builder after the upstream converter is
retired (standalone refactor, issue #156). `tools/validate.py` imports
`build_principles_index` from here to check index drift.
"""

from __future__ import annotations

import re
from pathlib import Path

PRINCIPLE_GROUPS = [
    (
        "Core",
        [
            "principle-laziness-protocol",
            "principle-foundational-thinking",
            "principle-redesign-from-first-principles",
            "principle-subtract-before-you-add",
            "principle-minimize-reader-load",
            "principle-outcome-oriented-execution",
            "principle-experience-first",
            "principle-exhaust-the-design-space",
            "principle-build-the-lever",
            "principle-attack-the-premise",
        ],
    ),
    (
        "Architecture",
        [
            "principle-model-the-domain",
            "principle-boundary-discipline",
            "principle-type-system-discipline",
            "principle-make-operations-idempotent",
            "principle-migrate-callers-then-delete-legacy-apis",
            "principle-separate-before-serializing-shared-state",
        ],
    ),
    (
        "Verification",
        [
            "principle-prove-it-works",
            "principle-fix-root-causes",
            "principle-sequence-verifiable-units",
            "principle-test-behavior-not-implementation",
        ],
    ),
    (
        "Delegation",
        [
            "principle-guard-the-context-window",
            "principle-never-block-on-the-human",
        ],
    ),
    (
        "Meta",
        [
            "principle-encode-lessons-in-structure",
        ],
    ),
]

_PRINCIPLES_HEADER = (
    "## Principles\n\n"
    "Read the leaf skill in full for any principle you apply. "
    "Each entry names when it applies.\n\n"
)

class ConvertError(RuntimeError):
    pass

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
            if rest in (">", ">-", "|", "|+", "|-"):
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
    for slug, (_title, _desc) in entries.items():
        if f"(**{slug}**)" not in block:
            drift.append(f"missing entry: {slug}")
    return block, drift
