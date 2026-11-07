#!/usr/bin/env python3
"""Assert the hermes-agent pin in validate-gold.yml is well-formed.

Slimmed for the standalone refactor (issue #156, drop PR): the upstream pin
lockstep and the NOTICE-vs-plugin version coupling both retired when the
converter was dropped. The HERMES_PIN checks below survive.

Exit codes: 0 pin is well-formed; 1 mismatch or malformed; 2 unreadable input.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]

# HERMES_PIN: full lowercase 40-char SHA, declared exactly once, in validate-gold.yml
HERMES_PIN_RE = re.compile(r"^\s*HERMES_PIN:\s*(\S+)", re.MULTILINE)
HERMES_PIN_WORKFLOW = "validate-gold.yml"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def check_hermes_pin(root: Path = ROOT) -> tuple[int, list[str]]:
    """Verify HERMES_PIN: full lowercase 40-char SHA, declared exactly once in
    validate-gold.yml, and named in CONTRIBUTING.md (issue #129 item 2)."""
    report: list[str] = []
    problems: list[str] = []

    hermes_wf = root / ".github" / "workflows" / HERMES_PIN_WORKFLOW
    if not hermes_wf.is_file():
        problems.append(f"HERMES_PIN: {HERMES_PIN_WORKFLOW} is missing; cannot verify pin")
        if problems:
            report.extend(f"FAIL: {p}" for p in problems)
            return 1, report
        return 0, report

    try:
        text = hermes_wf.read_text(encoding="utf-8")
    except OSError as exc:
        problems.append(f"cannot read {HERMES_PIN_WORKFLOW}: {exc}")
        report.extend(f"FAIL: {p}" for p in problems)
        return 1, report

    # Count ALL HERMES_PIN declarations in the document.
    all_pin_values: list[str] = []
    top_level_pin_values: list[str] = []

    try:
        composed = yaml.compose(text)
    except yaml.YAMLError as exc:
        problems.append(f"{HERMES_PIN_WORKFLOW} is not valid YAML: {exc}")
        composed = None

    def _walk_all_pins(node):
        """Recursively collect all HERMES_PIN values in the document."""
        if isinstance(node, yaml.MappingNode):
            for key_node, val_node in node.value:
                key = key_node.value if hasattr(key_node, "value") else str(key_node)
                if key == "HERMES_PIN":
                    v = val_node.value if hasattr(val_node, "value") else None
                    all_pin_values.append(v)
                _walk_all_pins(val_node)
                _walk_all_pins(key_node)
        elif isinstance(node, yaml.SequenceNode):
            for item in node.value:
                _walk_all_pins(item)

    if composed is not None:
        _walk_all_pins(composed)

    # Top-level env: HERMES_PIN
    if composed is not None and isinstance(composed, yaml.MappingNode):
        for key_node, val_node in composed.value:
            key = key_node.value if hasattr(key_node, "value") else str(key_node)
            if key == "env" and isinstance(val_node, yaml.MappingNode):
                for ek, ev in val_node.value:
                    ek_name = ek.value if hasattr(ek, "value") else str(ek)
                    if ek_name == "HERMES_PIN":
                        v = ev.value if hasattr(ev, "value") else None
                        top_level_pin_values.append(v)

    hermes_values = top_level_pin_values

    # Reject overrides: if HERMES_PIN appears outside top-level env, fail.
    if len(all_pin_values) != len(top_level_pin_values):
        problems.append(
            f"HERMES_PIN declared outside top-level env: "
            f"{len(all_pin_values) - len(top_level_pin_values)} override(s) found"
        )

    # Also check duplicate keys anywhere in the document.
    # (reuse simple duplicate detection)
    dupes = []
    if composed is not None:

        def _dup_walk(n, path=""):
            """Recursively detect duplicate mapping keys."""
            if isinstance(n, yaml.MappingNode):
                seen: set[str] = set()
                for key_node, val_node in n.value:
                    key = key_node.value if hasattr(key_node, "value") else str(key_node)
                    if key in seen:
                        dupes.append(key)
                    seen.add(key)
                    _dup_walk(val_node)
                    _dup_walk(key_node)
            elif isinstance(n, yaml.SequenceNode):
                for item in n.value:
                    _dup_walk(item)

        _dup_walk(composed)
    if "HERMES_PIN" in dupes:
        problems.append(f"HERMES_PIN declared multiple times in {HERMES_PIN_WORKFLOW}")

    if len(hermes_values) != 1 and "HERMES_PIN" not in dupes:
        # If duplicates collapsed, hermes_values may still show 1; rely on dupes check above.
        if len(hermes_values) != 1:
            problems.append(
                f"HERMES_PIN: expected exactly one declaration in "
                f"{HERMES_PIN_WORKFLOW}, found {len(hermes_values)}"
            )

    if len(hermes_values) == 1:
        hv = hermes_values[0]
        if not isinstance(hv, str) or not SHA_RE.fullmatch(hv):
            problems.append(f"HERMES_PIN is not a full lowercase 40-char SHA: {hv!r}")
        else:
            report.append(f"  {HERMES_PIN_WORKFLOW}: HERMES_PIN {hv}")

    contributing = root / "CONTRIBUTING.md"
    if contributing.is_file():
        if "HERMES_PIN" not in contributing.read_text(encoding="utf-8"):
            problems.append("HERMES_PIN is not named in CONTRIBUTING.md")
    else:
        problems.append("CONTRIBUTING.md missing; cannot verify HERMES_PIN is named")

    if problems:
        report.extend(f"FAIL: {p}" for p in problems)
        return 1, report
    return 0, report

def main(argv: list[str] | None = None) -> int:
    """CLI entry point for check_pins."""
    ap = argparse.ArgumentParser(prog="check_pins.py", description=__doc__)
    ap.add_argument("--root", type=Path, default=ROOT, help="repository root")
    args = ap.parse_args(argv)
    # HERMES_PIN (issue #129)
    hcode, hreport = check_hermes_pin(args.root)
    hstream = sys.stderr if hcode else sys.stdout
    for line in hreport:
        print(line, file=hstream)
    if hcode == 0:
        print("hermes pin: verified")
    return hcode


if __name__ == "__main__":
    raise SystemExit(main())
