---
name: hermes-troubleshooting
description: >-
  Use when the Hermes host itself looks broken (gateway down, TUI slow, MCP not
  loading, commands not firing) and poteto-mode should hand off to the
  `hermes-guide` diagnosing skills when they are installed.
---

# Hermes troubleshooting

This skill does **not** diagnose Hermes itself. It routes to the
`hermes-guide` plugin’s `diagnosing-*` skills when that plugin is installed —
and tells the user where to install it when it is not.

## 0. Preflight

Run `hermes doctor` first and record its output. A passing doctor is one
data point, not a proof of health — if the reported runtime symptom persists
(gateway, TUI, MCP, cron, voice, or other scope), continue to step 1.

## 1. If `hermes-guide` is installed

The plugin registers exactly one router skill — `hermes-guide:start` (in
`.hermes/plugins/hermes-guide/plugin-skills/start/SKILL.md`). Its
`diagnosing-*` playbooks live in the separate tap, not in that plugin file.
Load `hermes-guide:start` first (via `skill_view` id
`agent-plugin-hermes-guide-<digest>:start`, or `/hermes-guide:start` in a live
session). It routes to `hermes guide` and the correct `diagnosing-*` playbook
once the tap is present. To make a playbook loadable: after `hermes skills tap add
iap/hermes-guide`, also run `hermes skills install iap/hermes-guide/skills/diagnosing-triage`
(and the selected symptom-specific `diagnosing-*` skill). Adding the tap alone
does not install the playbooks.

Headless (`hermes -z` / one-shot): name the target skill explicitly, e.g.
`hermes -z "Use the diagnosing-path skill: …"` — skill auto-discovery does not
fire there.

## 2. If `hermes-guide` is not installed

Ask the user to install `iap/hermes-guide` (`hermes plugins install iap/hermes-guide --enable`,
`requires_hermes >=0.21`), plus its tap for the `diagnosing-*` playbooks
(`hermes skills tap add iap/hermes-guide`, then `hermes skills install
iap/hermes-guide/skills/diagnosing-triage` and the selected symptom-specific
skill — adding the tap alone does not install playbooks; see §1). `hermes guide`
is a Guide plugin command too, so do not suggest it until the plugin is
installed and enabled. Do not copy the 22 diagnosing skills into this package —
the plugin is the source of truth.

## 3. Stay in scope

- Only hand off after the report shows a host-level symptom that survives
  `hermes doctor`, or `hermes guide` reports `broken`/`unknown`. Returning to
  poteto-mode routing while the symptom still reproduces is a mis-triage.
- If a diagnosis identifies a pstack-side defect (banned construct, missing
  skill, panel mismatch), file it here (`iap/pstack-hermes`) — not upstream.
  Hermes host defects that reproduce with pstack disabled belong to
  `NousResearch/hermes-agent`.
