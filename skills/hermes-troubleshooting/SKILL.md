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

Run `hermes doctor` first. If it passes, the host is healthy — do not load
any diagnosing skill; the problem is in this task, not Hermes.

## 1. If `hermes-guide` is installed

1. Load `skill_view` id `agent-plugin-hermes-guide-<digest>:diagnosing-triage`
   (or `/hermes-doctor` in a live session).
2. Pick the `diagnosing-*` skill from the triage table for the symptom
   (`diagnosing-path`, `diagnosing-gateway`, `diagnosing-runtime`, …).
3. Follow that playbook; report its commands and the result back here.

Headless (`hermes -z` / one-shot): name the target skill explicitly, e.g.
`hermes -z "Use the diagnosing-path skill: …"` — skill auto-discovery does not
fire there.

## 2. If `hermes-guide` is not installed

Ask the user to install `iap/hermes-guide` (`hermes plugins install iap/hermes-guide --enable`,
`requires_hermes >=0.21`), or use the compiled guide path with
`hermes guide` / `hermes guide <scope>` (exit `0` healthy, `1` broken/unknown, `2` bad
scope). Do not copy the 22 diagnosing skills into this package — the plugin is
the source of truth.

## 3. Stay in scope

- This is a **host router**, not a task fix. Once the host is ruled healthy,
  return to poteto-mode routing.
- If a diagnosis identifies a pstack-side defect (banned construct, missing
  skill, panel mismatch), file it here (`iap/pstack-hermes`) — not upstream.
  Hermes host defects that reproduce with pstack disabled belong to
  `NousResearch/hermes-agent`.
