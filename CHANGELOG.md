# Changelog

All notable changes to the pstack-hermes port tooling will be documented in this file.

## [Unreleased]

### Fixed
- Delegation phrasing residuals: collapsed doubled `delegate_task` fragments in reflect (reviewers + synthesizer calls), reworded unbackticked Cursor leftovers (poteto-mode "omit Task `model`" -> inherit-parent semantics, how "Task subagent" -> delegate subagent)
- README differences contract: replaced the stale "nothing else modified" claim with the actual pass register (T8/T9/T10, Phase-2A, T11) and a pointer at `.build-provenance.txt` as the authoritative record; documented the `docs/guide/` exclusion; fixed off-by-one cross-reference (see 9 -> see 8)
- Ban-list inconsistency: unified delegation-vocab ban list under `bans.py` (single source of truth, 6 tokens)
- Model-slug drift: weekly CI re-verifies configured slugs against the live OpenRouter catalog
- Panel dedup guard: rejects duplicate provider slugs inside a role array; `inherit-parent` selector exempt
- Empty catalog guard: `slug_drift.py` raises on empty/malformed catalog instead of reporting every slug as missing
- Malformed JSON: local input failures return exit 2 (tool error) instead of crashing with exit 1 (misclassified as drift)
- Issue lookup failure: workflow fails instead of creating duplicate tracking tickets
- Workflow concurrency: overlapping runs are serialized, not cancelled
- Stale version reference: removed "hermes v0.20.5" from README template
- Stale line numbers: removed source line number references that drift across versions
- Roadmap promise: removed "expected in a future release" claim from README template

### Added
- `tools/slug_drift.py` — model-slug drift check against provider catalog
- `.github/workflows/model-drift-watch.yml` — weekly model-slug drift watch
- `## Environment` section in PR template (OS / Shell / Hermes version)
- Update instructions in README (uninstall + reinstall workflow)

### Changed
- convert.py: 4 specific-first `DELEGATION_MAP` pairs + `T9_MAP[19]` anchor updated to the collapsed intermediate text (anchor audit 78 -> 82)
- PR template: replaced hand-enumerated 2-token ban list with reference to `tools/bans.py`
- CONTRIBUTING.md: updated ban-list documentation to reflect 6-token set
- README.md: clarified install command (shorthand form required)

## [0.3.0] - 2026-09-09

### Added
- Initial converter/validator tooling
- Atomic builds with rollback
- Fail-loud anchor audit
- Scanner gate with shared banned-construct source of truth
- CI: 2-OS matrix, SHA gates, determinism proof, unit tests, lint
- Weekly upstream-drift watch
