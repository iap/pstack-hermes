# Pull request checklist

## Scope
- What changed (one line):
- Which platform(s) this affects: hermes / Cursor dual-load / both

## Verification (paste evidence)
- [ ] `python3 convert.py` runs clean (if the converter or a skill changed)
- [ ] `python3 validate.py --package pstack` exit 0
- [ ] `hermes plugins doctor pstack --ci` exit 0 (if install-relevant)
- [ ] No banned constructs: `subagent_type`, `generalPurpose`, Cursor model slugs in new code, `tailscale.com/install.sh`
- [ ] Provenance consistency: `.build-provenance.txt` still records the pinned upstream SHA

## Attribution
- [ ] Upstream (MIT, Lauren Tan) is preserved and this PR is attributable
