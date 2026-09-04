"""Single source of truth for the install-scanner-clean banned constructs.

Consumed by tools/validate.py (F-publish check) and tools/scanner_gate.py
(the CI gate) so the two can never drift apart. The scan scope mirrors the
real hermes install scanner: EVERY UTF-8-decodable file in the package,
not just .md/.json/.txt.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

# Package-wide: no exceptions. These mirror hermes install-scanner verdicts
# that BLOCK installs and cannot be --force overridden.
SECURITY_BANS: tuple[tuple[str, str], ...] = (
    ("tailscale.com/install.sh", "privilege escalation: curl|sudo sh installer"),
    ("FOR_AGENTS.md", "persistence: copy-instructions pattern"),
    ("http://127.0.0.1:4173", "network: hardcoded loopback endpoint literal"),
)

# Hermes-facing surface only. The Cursor dual-load surface (agents/,
# .cursor-plugin/) and the build provenance (which documents the fixes by
# name) are exempt.
DELEGATION_VOCAB_BANS: tuple[str, ...] = ("subagent_type", "generalPurpose")
VOCAB_EXEMPT_PREFIXES: tuple[str, ...] = ("agents/", ".cursor-plugin/", ".build-provenance.txt")


def iter_text_files(pkg: Path) -> Iterator[tuple[str, str]]:
    """Yield (posix-rel-path, text) for every UTF-8-decodable file in pkg."""
    for p in sorted(pkg.rglob("*")):
        if not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        yield p.relative_to(pkg).as_posix(), text


def find_violations(pkg: Path) -> list[str]:
    """Return one human-readable line per banned construct found in pkg."""
    bad: list[str] = []
    for rel, text in iter_text_files(pkg):
        for needle, why in SECURITY_BANS:
            if needle in text:
                bad.append(f"{rel}: {needle} ({why}) [security, package-wide]")
        if not rel.startswith(VOCAB_EXEMPT_PREFIXES):
            for needle in DELEGATION_VOCAB_BANS:
                if needle in text:
                    bad.append(f"{rel}: {needle} [delegation vocab, hermes-facing]")
    return bad
