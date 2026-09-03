# pstack (hermes agent-plugins-v1 package)

Phase-0 conversion of **pstack v0.14.4** for the Hermes Agent platform's
portable plugin path. Upstream: <https://github.com/cursor/plugins/tree/main/pstack>
(MIT, Copyright (c) 2026 Lauren Tan). Conversion provenance: see `.build-provenance.txt`;
regenerate with `python tools/convert.py --source <pstack-clone> --out <package-dir>`.

## What hermes loads

- **45 skills** via the agent-plugins-v1 portable path
  (24 workflow/mode skills + 21 `principle-*` skills):
  single-level `skills/<dir>/SKILL.md`, immediate children only.
- Root `plugin.json` — the strict agent-plugins-v1 manifest hermes probes at the
  package root: exact `$schema` URL, 9 whitelisted fields
  ($schema, name, version, description, author, homepage, repository, license, keywords).

## What stays inert on hermes (for now)

- `agents/` (poteto-agent, comment-sicko) — the portable path discovers skills and
  mcp.json only; no agent registration exists in hermes v0.20.5. Kept for Cursor
  dual-load and a Phase-2 native wrapper.
- `automations/benny/` — **excluded** from this package: the install scanner
  flags its copy-instructions as persistence patterns (verdict: dangerous),
  and Phase 4 rebuilds it as hermes cron/loop jobs anyway.
- `skills/make-bot-ui/` — **excluded**: its Tailscale setup script trips the
  privilege-escalation scanner (F33); deepest vendor coupling. The slot is
  filled by `skills/hermesbot/` — a hermes-native control-surface skill
  injected from `tools/assets/hermesbot/SKILL.md` at build time.
- Executable scripts shipped inside skills (e.g. `skills/poteto-mode/scripts/`) —
  copied verbatim; the loader never executes them.

## How to invoke on hermes

Portable plugin skills are **opt-in**: they do not enter the system-prompt
`<available_skills>` index. Load a skill explicitly with `skill_view` using the
namespaced id `agent-plugin-pstack-<digest>:<skill-name>`, where `<digest>` is the
first 8 hex chars of the sha256 of the plugin key (stable while the install
directory keeps the name `pstack`).

Optional slash-command route (no code): add this package's `skills` directory to
`skills.external_dirs` in `%LOCALAPPDATA%\hermes\config.yaml` and the hub scanner
registers all 45 skills as `/<name>` slash commands (agent/skill_commands.py:424).
Trade-offs: skills enter the prompt index with 60-char descriptions and lose the
plugin namespace; the portable path itself registers zero commands
(plugins.py:5088-5138).

## Install path (Windows)

Copy this package directory to `%LOCALAPPDATA%\hermes\plugins\pstack`, then add
`pstack` to `plugins.enabled` in `%LOCALAPPDATA%\hermes\config.yaml`.

## Cursor dual-load

`.cursor-plugin/plugin.json` is preserved unchanged, so this same directory still
loads as a Cursor plugin. Hermes probes only `<root>/plugin.json` and never reads
`.cursor-plugin/`.

## Differences from upstream (the conversion gate)

1. Root `plugin.json` injected with the exact agent-plugins-v1 `$schema` URL and a
   whitelisted field set (upstream Cursor fields `displayName`, `category`, `tags`,
   `skills`, `agents` are omitted — unknown fields produce loader diagnostics).
2. `skills/poteto-mode/SKILL.md`: frontmatter `name: Poteto Mode` -> `name: poteto-mode`.
3. `skills/grokbot/` container and `skills/make-bot-ui/` are **excluded** (see 9);
   the loader only sees immediate children of `skills/` anyway.
4. Text normalization to UTF-8 without BOM and LF line endings.
5. **R1**: the poteto-mode principles index is regenerated from the 21 principle
   leaves at build time — the leaves are the single source of truth, so the
   historical four-way duplication (index/leaf/README/guide) cannot drift here.
6. **F16**: `check-plan.mjs` reads the fast-lane slug from `PSTACK_FAST_LANE`
   (default `grok-4.6-fast-xhigh`) instead of a hardcoded literal; the
   multi-phase-plan template documents the override.
7. **F10-F12**: `worktree-audit.sh` detects GNU vs BSD `stat`/`date` at runtime
   (`stat_mtime`/`date_epoch` helpers) and no longer truncates worktree paths
   containing spaces (verified on GNU/Linux; unchanged behavior on macOS).
8. **F-publish**: `automations/benny/` and `skills/make-bot-ui/` excluded —
   the hermes install scanner blocks packages whose scan verdict is
   "dangerous" (benny copy-instructions + make-bot-ui Tailscale), --force
   cannot override, and both are Phase-4/what-not-to-port items anyway.
   The make-bot-ui slot is filled by hermes-native `skills/hermesbot/`
   (injected from `tools/assets/hermesbot/SKILL.md`): a control-surface
   skill on the hermes gateway's own webhook stack (`X-Webhook-Signature-V2`
   HMAC routes), `hermes send`, and `hermes peer` — no Tailscale, no
   third-party bot runtime.
9. **G1**: a delegation escape hatch added to the Feature playbook and the
   poteto-mode Subagents section — surgical, fully-specified edits to files
   already resident in context may be implemented in-thread, provided a leaf
   delegate reviews the diff (review separation preserved; fixes the
   deviation observed in the first live usage run).

Nothing else in any SKILL.md was modified.

---

Adapted for Hermes Agent plugin compatibility from github.com/cursor/plugins pstack..
