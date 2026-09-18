# Changelog

All notable changes to the pstack-hermes port tooling will be documented in this file.

## [0.4.3] - 2026-09-18

### Added
- `publish-plugin.yml`: CI publisher that publishes the validated built package to the plugin-only dist repo `iap/pstack` (build output; append-only commits so installed clones can fast-forward — history is never rewritten; skipped with a warning until `PLUGIN_DIST_TOKEN` is configured; every real publish is tagged `pstack-<date>-<sha>`, because the plugin catalog admits only repos with real tags). The dist repo's tree root is the package, enabling the root install shorthand `hermes plugins install iap/pstack --enable` — no subdir — and in-place `hermes plugins update pstack` (root installs keep `.git`; verified against the hermes installer source). Requires the one-time `PLUGIN_DIST_TOKEN` secret (fine-grained PAT, contents: read/write on the dist repo only).
- Agent-facing docs: `AGENTS.md` (harness identity, generated-tree rule, hermes-vs-Cursor vocabulary, primitive mapping) and a CONTRIBUTING rewrite (orientation, Bun setup, common-task recipes, publish stage).
- `docs/USING.md` "Customizing skills": three routes by intent (edit in place for small tweaks, fork the dist repo for owned variants, skill taps for adding new skills alongside) with the keep-hermes-vocabulary warning for end users.
- `validate.check_conflict_markers`: static-stage gate banning unambiguous VCS conflict-marker line-starts package-wide (a bare `=======` stays legal as a setext underline; node_modules exempt), with regression tests.

### Changed
- README install routes reorganized: root install via the dist repo is primary; the `iap/pstack-hermes/pstack` subdir install is documented as the legacy route (still works). Update instructions split by route (in-place update for root installs; reinstall for subdir installs).

### Fixed
- Converter: `T13_MAP`'s frontier-provider entry was anchored on text that only exists *after* the `T13_MAP` forge-wording entry and `T14_MAP`'s first entry run — an ordering that can never match a clean pinned clone (the local 2026-09-14 build predated the map edit and its `pstack/` was stale). Re-anchored the entry to the pinned paragraph, pruned the two subsumed entries (`T13_MAP` forge-wording line, `T14_MAP` first entry — their intent is carried by the full-paragraph provider-selection rewrite), and rebuilt from the clean pin: `orchestrate.md` and the package README now carry the T15 provider-selection wording, with the anchor audit passing against a fresh clone of `93b00b8`.
- T15b robustness (carried through the converter after a direct-to-generated-file edit was caught by the reproducibility gate): GitHub-native discovery now scopes itself to an explicit `--prs` pin instead of validating every PR in the repository as one stack, `gh pr list` passes an explicit `--limit 100` so connected stacks beyond 30 PRs are not silently truncated, and auto-provider fallback is persisted into `frontier.json` as a `fallback` field (which providers were skipped) so a Graphite → GitHub fallback is coordinator-visible instead of silent. The GitLab provider remains reserved ("not implemented yet") pending a reviewed `glab` integration.

## [0.4.2] - 2026-09-13

### Added
- Docs: `docs/ADAPTATIONS.md` (adaptations ledger, primitive mapping, deliberately-not-ported), `docs/RUNBOOK-upstream-drift.md` (re-pin procedure), `docs/USING.md` (invocation model, first run, expectations). Review round: the upstream closure date corrected to 2026-09-10 (closed unmerged; the API attests no closer), and the panel-consumer claim now quotes the actual role-line phrases.
- `slug_drift.py --prose`: scans skill markdown for backtick-quoted model-slug defaults (including vendor/model forms) once the provider catalog loads; `model-drift-watch.yml` passes `--prose` and reports prose-only findings as informational (exit 0) — a catalog tool error (exit 2) skips the scan, since the panel slugs are verified against the loaded catalog first (#25/#29)
- CONTRIBUTING: document the GitHub alert-callout style for docs — and where it does not apply (#30)

### Changed
- Structure hygiene: `pstack/` marked `linguist-generated` in `.gitattributes` (diffs collapse in review) and PR guidance now requires `rebuilt from pin <sha>` in the body; README documents the two version lines (package `0.14.8` vs repo `v0.4.x`) and corrects the transform range to T1–T13; the package README's Known limitations gains the optional-MCP-servers note (template change + rebuild); the PR template gains the matching conditional `pstack/` rebuild-disclosure fields
- Main README rewritten Hermes-first: first-screen unofficial-port identity (not affiliated with Cursor or Lauren Tan; Cursor users go upstream), install up front, Cursor dual-load demoted to a trailing incidental/unsupported note; layout line corrected T1–T11 to T1–T12
- Converter package-README template: `uv run --frozen` regenerate command and a CLI-install section replacing the manual-copy path; T13 gains the missed orchestrate.md `cursor-team-kit` anchor — rebuilt package from pinned `93b00b8` now carries zero `cursor-team-kit` references in shipped skills
- T13 conversion pass: residual Cursor-vendor coupling reworded across the package — `cursor-team-kit` references (a deslop pass, `control-ui`/`control-cli`), the cloud-agent fleet wording, and Graphite (`gt`) phrasing; `T13_MAP` wired into the conversion flow and the anchor audit (115/115)
- PR template: replace the unrunnable `python3 convert.py` checkbox with the real `uv run --frozen tools/convert.py --source <pstack-clone> --out pstack` invocation (the script lives in `tools/` and requires `--source`); add the `tools/scanner_gate.py --package pstack` line that actually enforces the banned-construct checkbox; note the gateway-restart warning in the doctor line as unrelated noise
- SECURITY.md reporting triage: issues caused by this port (adaptations, exclusions, configuration, install) belong to this repository; upstream reports are reserved for genuine platform or original-project defects — including a Hermes defect that surfaces only while a plugin is installed
- Issue chooser: the port-problem link now opens the Bug report form directly (`issues/new?template=bug_report.yml`) instead of the All-issues list

### Fixed
- Residual doc defects: the package README no longer says it rebuilds benny as "hermes cron/loop jobs" (the template is corrected at the source, so the generated line is right by construction), and the control-surface replacement is properly capitalised. The two dead T13 maps — `T13_PRINCIPLE_MAP` and `T13_README_MAP`, both defined but never applied or audited — are removed.

## [0.4.1] - 2026-09-10

### Changed
- T12: Cursor built-in `/loop` and `/goal` references reworded to hermes-native mechanisms — gateway cron jobs as the wake/scheduler (autonomous-run, autopilot-full, autopilot-stack, babysit, bug-fix, multi-phase-plan, shipping, visual-parity) and an armed `goal.md` in the agent store replacing the goal primitive; trigger phrases de-slashed ("loop until X"); plan checker (`check-plan.mjs`) marker aligned to accept the new mechanism

### Removed
- Executed pipeline-hardening plan doc dropped from `docs/superpowers` (#23). The plan shipped in v0.4.0 and the repo's own `.gitignore` already places agent session artifacts (plans/notes) outside the repo.

## [0.4.0] - 2026-09-09

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
