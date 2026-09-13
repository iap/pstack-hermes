# Pull request checklist

## Scope
- What changed (one line):
- Which platform(s) this affects: hermes / Cursor dual-load / both

## Environment
- OS: Windows / macOS / Linux
- Shell: bash / PowerShell / zsh
- Hermes version: (output of `hermes --version`)

## Verification (paste evidence)
- [ ] `uv run --frozen tools/convert.py --source <pstack-clone> --out pstack` runs clean
      (converter or a skill changed; clone upstream at the pinned SHA if you don't have one)
- [ ] `uv run --frozen tools/validate.py --package pstack` exit 0
- [ ] `uv run --frozen tools/scanner_gate.py --package pstack` exit 0
- [ ] `hermes plugins doctor pstack --ci` exit 0 (install-relevant; ignore the
      "gateway restart" warning — it is unrelated to this plugin)
- [ ] Provenance consistency: `.build-provenance.txt` still records the pinned upstream SHA

## Attribution
- [ ] Upstream (MIT, Lauren Tan) is preserved and this PR is attributable
