# NOTICE

pstack-hermes — unofficial community port of Cursor's pstack agent method
to the Hermes Agent platform.

This file records attribution for the upstream work and for the platform
this port targets. It does not replace LICENSE, which governs the
distribution of this package.

## Upstream: pstack (Cursor plugins)

- Project: pstack v0.15.5
- Upstream repository: https://github.com/cursor/plugins
- Upstream path: pstack/
- Author: Lauren Tan
- License: MIT — Copyright (c) 2026 Lauren Tan. See LICENSE at the
  repository root for the full text, including the adaptation line:
  "Adapted for Hermes Agent plugin compatibility from
  github.com/cursor/plugins pstack."
- This port was originally built from a pinned upstream clone
  (`c47b1284`, v0.15.5). The standalone refactor (#156) retired the
  upstream converter: the shipped package (plugin.json, skills/,
  config/, assets/, README.md, LICENSE) is now hand-written source in
  this repository, edited directly. The final upstream SHA survives as
  historical context in CHANGELOG.md.

## Platform: Hermes Agent

- Runtime target: Hermes Agent (NousResearch/hermes-agent),
  https://github.com/NousResearch/hermes-agent
- Hermes Agent is a separate project and is not bundled in this
  package. This port adapts upstream Cursor vocabulary and mechanics
  to Hermes primitives (delegate_task, clarify, session_search,
  hermes cron). Cursor is upstream attribution only, not the
  implementation or verification path.
- Platform bugs that reproduce with this plugin disabled belong
  upstream at NousResearch/hermes-agent. Port-specific adaptations,
  tooling, and configuration belong to this repository.

## This port: pstack-hermes

- Repository: https://github.com/iap/pstack-hermes
- Package identity: pstack (plugin.json, agent-plugins-v1 manifest)
- Hand-written tooling and docs in this repository (tools/,
  tools/assets/, docs/, AGENTS.md, CONTRIBUTING.md, SECURITY.md,
  CHANGELOG.md, NOTICE.md) are this project's own additions to
  the upstream port. They are not part of the upstream copyright
  notice in LICENSE, which names only Lauren Tan for the
  upstream pstack material. No separate copyright or license
  grant for the port additions is recorded in LICENSE.
- Deliberate exclusions from the shipped package, per the install
  scanner contract: directory exclusions are enforced by
  tools/validate.py (F-publish checks); banned content is enforced by
  tools/scanner_gate.py in CI, sharing definitions with
  tools/bans.py:
  automations/benny/ and skills/make-bot-ui/ are not shipped.
  The make-bot-ui slot is filled by the Hermes-native hermesbot
  skill (skills/hermesbot/SKILL.md).
- Stack tooling referenced by the skills (Graphite `gt`, GitHub `gh`)
  is external and not bundled. Graphite and GitHub are trademarks
  of their respective owners.

## No warranty

The upstream material is provided "AS IS", without
warranty of any kind, as stated in LICENSE. The upstream
authors and copyright holders are not liable for any claim,
damages, or other liability arising from use of this package.
No warranty or liability statement for the port additions is
recorded in LICENSE.
