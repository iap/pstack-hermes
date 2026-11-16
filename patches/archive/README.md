# Archived fork patches — reference only, not gated

These four patches were proposed against `NousResearch/hermes-agent` in
September 2026. The upstream PRs were closed unmerged, and the gaps they
address are **still present** in the tree checked on 2026-11-16 UTC:
Hermes `v0.22.5+1468.g8d617f5`, commit `8d617f52fe3fdf29a222a42d29c72645329e6524`.
They are kept here as a record of the port's findings, not as a fix path.

The commit each patch was originally authored against is **not recorded** —
that omission is part of why they are archived.

| patch | target | still present in v0.22.5? | evidence |
|---|---|---|---|
| `hermes-fork-oneshot-cwd-v2.patch` | `hermes_cli/oneshot.py` | **yes** — oneshot never tells the model its cwd | `ephemeral_system_prompt=skills_prompt` only (no cwd note) |
| `hermes-fork-oneshot-cwd.patch` (v1) | `hermes_cli/oneshot.py` | yes, same gap | v1 is API-coupled (`record_session_cwd`); v2 was preferred |
| `hermes-fork-portable-diagnostics.patch` | `hermes_cli/agent_plugins.py` | **yes** — Cursor-only fields get a generic "ignored unknown top-level field" diagnostic | `_validate_manifest` loop |
| `hermes-fork-scanner-plugin-root.patch` | `tools/skills_guard.py` | **yes** — the 50-file cap applies to a whole plugin root | `if file_count > MAX_FILE_COUNT:` |

## Decision (2026-11-16 UTC)

Archive them. Carrying live patches against a moving upstream is a maintenance
tax the project was already paying in anxiety rather than in effect: none is
required for the package to load, validate, or install, and the weekly
`patch-health` job could only ever report that they no longer apply.

The gaps are recorded, not fixed. If one becomes load-bearing again, the honest
route is a new upstream issue with the reproduction in `docs/PATCHES.md`, then a
patch rebased against the then-current tree — not a silent revive of these.

## Consequences to remember

- `hermes -z` (oneshot) still does not seed a working directory. Eval prompts
  and any scripted oneshot use must pass absolute paths; see
  `tools/evals/README.md`.
- Portable Cursor-style plugin manifests still load with a generic warning
  instead of a component-level one.
- The per-skill file cap still applies to a plugin root that bundles many
  skills. Moving the same bundle into a subdirectory does not avoid it — the
  scanner treats that directory as the root. Installs that trip the cap need an
  upstream scanner fix or a genuinely smaller package.
