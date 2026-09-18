# AGENTS.md

> [!IMPORTANT]
> This repository is **pstack-hermes** — the unofficial community port of
> Cursor's *pstack* agent-method plugin to the **Hermes Agent** platform
> (`NousResearch/hermes-agent`). The runtime target is **hermes, never
> Cursor**. Read "Hermes vs Cursor" below before changing anything.

Instructions for AI coding agents (and humans in a hurry) working **on this
repository**. For using the shipped plugin, read [docs/USING.md](docs/USING.md)
instead. The full contributor contract is
[CONTRIBUTING.md](CONTRIBUTING.md); the change ledger is
[docs/ADAPTATIONS.md](docs/ADAPTATIONS.md).

## The one rule that outranks everything else

> [!WARNING]
> **`pstack/` is generated output. Never hand-edit it.** It is rebuilt from
> the pinned upstream clone by `tools/convert.py` (atomic swap, byte-
> reproducible). Hand edits are wiped on the next rebuild and flagged as
> drift. To change the package: change the converter, rebuild, validate.
> Provenance for the current build lives in `pstack/.build-provenance.txt`.

Everything else in this file follows from that rule.

## Commands

```sh
uv sync                                            # pinned CPython 3.11 + dev group
uv run --frozen tools/convert.py  --source <pstack-clone> --out pstack   # rebuild package
uv run --frozen tools/validate.py                  # 4-stage ladder; must exit 0
uv run --frozen pytest -q                          # tooling unit tests
uv run --frozen ruff check tools                   # lint
```

The poteto-mode checker scripts carry their own Bun suite (CI runs it):

```sh
cd pstack/skills/poteto-mode/scripts
bun run test                                       # deps + `bun test orch watch-pr`
bun run typecheck                                  # deps + tsc --noEmit --strict
```

Maintainer-only, for install-relevant changes: `hermes plugins doctor pstack --ci`
(needs the hermes venv on your machine).

## Hermes vs Cursor — how not to confuse them

This repo constantly *mentions* Cursor because Cursor is the upstream. Cursor
appears in exactly three legitimate roles; anything Cursor-shaped outside
those roles is drift:

| Role | Where | Your obligation |
|---|---|---|
| Upstream source of truth | pinned clone `cursor/plugins` @ `93b00b8` (MIT © Lauren Tan); homepage/repo URLs in manifests; attribution lines | preserve verbatim — never rewrite, re-home, or "modernize" |
| Inert dual-load surface | `pstack/.cursor-plugin/`, `pstack/agents/` — kept so the same tree *structurally* loads as a Cursor plugin; hermes probes the root manifest only | leave untouched — do not fix, extend, or delete |
| Bug routing | upstream plugin bugs that reproduce without this port → `cursor/plugins`; hermes defects → `NousResearch/hermes-agent`; everything else → this repo's Issues | route reports correctly (see [SECURITY.md](SECURITY.md)) |

**Skills and tooling content speaks hermes vocabulary.** When writing or
editing converter output, docs, or tooling, use the hermes primitive — never
the Cursor one:

| Cursor / upstream primitive | Hermes treatment |
|---|---|
| `Task` subagents, `subagent_type`, `run_in_background` | `delegate_task` (persona via the task prompt; background execution) |
| `AskQuestion` | `clarify` |
| transcript files (`agent-transcripts/*.jsonl`) | `session_search` over the hermes session store |
| terminal `/loop` (sleep + wake) | recurring `hermes cron` wake |
| armed `/goal` | `goal.md` beside the plan in the agent store |
| `grokbot` / `make-bot-ui` (Tailscale bot) | `hermesbot` (gateway webhook + `hermes send` + `hermes peer`) |
| Cursor `create-skill` | hermes `skill_manage` |
| model config | `config/models.json` (18 roles; source `tools/assets/model-panel.json`) |

CI enforces this vocabulary: the delegation tokens and security needles in
`tools/bans.py`, plus the `HERMES_ADAPTATION_BANS` construct list in
`tools/validate.py`, are scanned across every decodable file in the package.
The full mapping rationale is [docs/ADAPTATIONS.md](docs/ADAPTATIONS.md) §2.

## Repo map — what is hand-written, what is generated

| Path | Nature | Rules |
|---|---|---|
| `pstack/` | **generated** (converter output; `linguist-generated`) | never hand-edit; review as build output |
| `pstack/.cursor-plugin/`, `pstack/agents/` | generated, inert on hermes | dual-load surface; leave as-is |
| `tools/` | hand-written (converter, validator, bans, scanner gate, slug drift, tests) | the source of package truth |
| `tools/assets/` | hand-written inputs the converter copies in (`model-panel.json`, `hermesbot/SKILL.md`) | edit here, then rebuild |
| `docs/` | hand-written (ADAPTATIONS ledger, USING, RUNBOOK, PATCHES) | a new converter pass requires a new ADAPTATIONS row |
| `patches/` | hand-written hermes-fork patches | documented in [docs/PATCHES.md](docs/PATCHES.md) |
| `.github/` | hand-written CI, labeler, issue templates | path-sensitive (see below) |
| `AGENTS.md`, `README.md`, `CONTRIBUTING.md`, `SECURITY.md`, `CHANGELOG.md` | hand-written | repo-level contract |
| `.venv/`, `.kilo/`, `pstack.tmp-build/`, `.pytest-tmp/` | local scratch / harness state | never commit |

## Hard rules (CI enforces all of these)

- **The pin moves in lock-step.** `UPSTREAM_PIN`
  (`93b00b89ef425a9c1bac0d0b317dfc49c930ac99`) is declared independently in
  three workflows — `ci.yml`, `release.yml`, `upstream-drift-watch.yml` — and
  all three must move together. Procedure: [docs/RUNBOOK-upstream-drift.md](docs/RUNBOOK-upstream-drift.md).
- **Anchors are audited.** A converter transform whose anchor matches nothing
  in the upstream build fails the build loudly. Never silence or force past
  the audit; re-anchor or prune, and record why.
- **Two version lines, never mixed.** The package keeps the upstream identity
  `0.14.8` (it is *not* renumbered by port releases); repository releases are
  the `v0.4.x` line tracked in `CHANGELOG.md`.
- **Encoding.** LF-only, no BOM, UTF-8 (`.gitattributes` + `validate.py`).
- **Every converter change is documented.** New pass or map change → matching
  row in `docs/ADAPTATIONS.md` with a reviewer check, and the rebuilt
  `pstack/` in the same PR with `rebuilt from pin <sha>` in the body.
- **Excluded upstreams stay excluded.** `automations/benny` and
  `skills/make-bot-ui` are omitted for install-scanner verdicts (their slot is
  filled by the repo-owned `hermesbot`); do not re-add them.
- **The dist repo is build output.** `iap/pstack` — the root install source —
  is written only by CI (`publish-plugin.yml`) as append-only commits from
  the validated pinned build; history is never rewritten there, because
  `hermes plugins update` fast-forwards installed clones. Never hand-push to
  it, and never point install docs at this dev
  repo's root: the install scanner scans the whole tree, and the dev tree
  (ban needles in `tools/`) can never be scanner-clean.

## Common traps

- Editing `pstack/skills/hermesbot/SKILL.md` directly — edit
  `tools/assets/hermesbot/SKILL.md` and rebuild.
- Hand-tuning `pstack/config/models.json` — edit
  `tools/assets/model-panel.json` and rebuild; `validate.py` checks they match.
- "Fixing" Cursor mentions that are attribution or the dual-load surface —
  those are correct as-is (see the table above).
- Rewriting hermes primitives back into Cursor vocabulary in skill prose —
  that is exactly what the bans exist to catch.
- Blurring the two install/update routes: the **root install**
  (`hermes plugins install iap/pstack`) keeps `.git` and updates in-place via
  `hermes plugins update pstack`; the **subdir install**
  (`iap/pstack-hermes/pstack`) strips `.git`, so it is updated by reinstall
  only. Docs must keep the two routes distinct.
