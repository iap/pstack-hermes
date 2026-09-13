<!--
Check a box only when it applies; otherwise leave it unchecked with an N/A note.
Paste evidence under each checked box — a bare check without output proves nothing.
Full gate list mirrors the CONTRIBUTING "Pull requests" section.
Attribution is standing policy in CONTRIBUTING.md (upstream MIT preserved
everywhere; provenance written by the converter) — no per-PR checkbox.
-->
# Pull request checklist

## Scope
- What changed (one line):
- Which platform(s) this affects: hermes / Cursor dual-load / both

## Generated package (complete only if this PR changes `pstack/`)
- Rebuilt from pin: `<sha>` (must match `.build-provenance.txt` `source_commit`)
- Converter change behind the rebuild: <pass/map, e.g. a `T13_MAP` entry>
- [ ] `pstack/` changes are converter output only — no hand edits

## Environment
- OS: Windows / macOS / Linux
- Shell: bash / PowerShell / zsh
- Hermes version: (output of `hermes --version`)

## Verification (paste evidence)
- [ ] `uv run --frozen tools/convert.py --source <pstack-clone> --out pstack` runs clean
      (converter or a skill changed; clone upstream at the pinned SHA if you don't have one)
      Evidence:
- [ ] `uv run --frozen tools/validate.py --package pstack` exit 0
      Evidence:
- [ ] `uv run --frozen tools/scanner_gate.py --package pstack` exit 0
      Evidence:
- [ ] `hermes plugins doctor pstack --ci` exit 0 (install-relevant; ignore the
      "gateway restart" warning — it is unrelated to this plugin)
      Evidence:
- [ ] Provenance consistency: `.build-provenance.txt` still records the pinned upstream SHA
