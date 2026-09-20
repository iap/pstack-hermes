# AGENTS.md

> [!IMPORTANT]
> This repository is **pstack-hermes** — the unofficial community port of
> Cursor's *pstack* agent-method plugin to the **Hermes Agent** platform
> (`NousResearch/hermes-agent`). The runtime target is **hermes**. Cursor is
> upstream attribution and an inert dual-load surface only — not the delivery
> path. Do not invent Cursor IDE, Graphite, or Cursor-plugin authoring
> workflows to implement or verify this package.

Instructions for AI coding agents (and humans in a hurry) working **on this
repository** to ship pstack onto hermes. End-user invoke/config:
[docs/USING.md](docs/USING.md). PR/release/re-pin procedures:
[CONTRIBUTING.md](CONTRIBUTING.md). Converter change ledger:
[docs/ADAPTATIONS.md](docs/ADAPTATIONS.md).

## The one rule that outranks everything else

> [!WARNING]
> **`pstack/` is generated output. Never hand-edit it.** It is rebuilt from
> the pinned upstream clone by `tools/convert.py` (atomic swap, byte-
> reproducible). Hand edits are wiped on the next rebuild and flagged as
> drift. To change the package: change the converter or `tools/assets/`,
> rebuild, validate. Provenance: `pstack/.build-provenance.txt`.

Everything else in this file follows from that rule.

## Change triage (30 seconds)

Default home for work is **this repo**. Escalate only when the table says so.

| If you need to… | Do this | Not this |
|---|---|---|
| Change skill prose, delegation wording, model panel, hermesbot, bans, docs, converter maps | Edit `tools/` / `tools/assets/` → rebuild → validate → (ledger row if converter changed) | Hand-edit `pstack/`; rewrite in Cursor vocabulary |
| Package validates / doctor is clean, but stock install misbehaves on hermes | File/fix in `NousResearch/hermes-agent`; `patches/` is **historical reference only** ([docs/PATCHES.md](docs/PATCHES.md)) | Paper over harness gaps with skill prose that claims nonexistent tools |
| Bug reproduces on upstream Cursor pstack *without* this port | Route to `cursor/plugins` ([SECURITY.md](SECURITY.md)) | "Fix" it in the converter as if it were a port bug |
| Touch `.cursor-plugin/`, `pstack/agents/`, attribution, excluded `benny` / `make-bot-ui` | Leave as-is (dual-load / scanner contract) | "Clean up", re-add, or modernize |

## Default work loop

```sh
uv sync
# 1. Edit the hand-written source of truth (tools/, tools/assets/, docs/, …)
# 2. Rebuild from a clone at the pinned upstream SHA:
uv run --frozen tools/convert.py --source <pstack-clone> --out pstack
# 3. Must exit 0:
uv run --frozen tools/validate.py
uv run --frozen pytest -q
uv run --frozen ruff check tools
```

Then:

1. If the converter/maps/assets that shape the package changed → add a row to
   [docs/ADAPTATIONS.md](docs/ADAPTATIONS.md) with a **reviewer check**, and
   include rebuilt `pstack/` in the same PR (`rebuilt from pin <sha>` in the body).
2. If the change is **install-relevant** (manifest, skill discovery, package
   layout) → `hermes plugins doctor` against the **installed dist package**
   (`hermes plugins doctor pstack --ci`, run from outside the repo — `pstack`
   resolves to the installed plugin id) or against the **branch-local build**
   (`hermes plugins doctor "$PWD/pstack" --ci`, run from the repo root —
   explicit path so it does not silently hit the installed dist).
3. Re-pin upstream only via
   [docs/RUNBOOK-upstream-drift.md](docs/RUNBOOK-upstream-drift.md) — never by
   hand-tuning `pstack/`.

Poteto-mode checker scripts (CI runs these):

```sh
cd pstack/skills/poteto-mode/scripts
bun run test        # deps + bun test orch watch-pr
bun run typecheck   # deps + tsc --noEmit --strict
```

## Where to edit

| Path | Nature | Rules |
|---|---|---|
| `pstack/` | **generated** (`linguist-generated`) | never hand-edit; review as build output |
| `pstack/.cursor-plugin/`, `pstack/agents/` | generated; inert on hermes | dual-load surface; leave as-is |
| `tools/` | hand-written converter, validator, bans, scanner gate, tests | source of package truth |
| `tools/assets/` | inputs the converter copies in (`model-panel.json`, `hermesbot/SKILL.md`) | edit here, then rebuild |
| `docs/` | ADAPTATIONS ledger, USING, RUNBOOK, PATCHES | converter pass → new ADAPTATIONS row |
| `patches/` | historical hermes-fork patch reference | not required to load/install; see PATCHES.md |
| `.github/` | CI, labeler, issue templates | pin SHA must stay in lock-step across workflows |
| `AGENTS.md`, `README.md`, `CONTRIBUTING.md`, `SECURITY.md`, `CHANGELOG.md` | hand-written | repo-level contract |
| `.venv/`, `.kilo/`, `pstack.tmp-build/`, `.pytest-tmp/` | local scratch | never commit |

## Hermes verify

Goal: prove the **built package** behaves on hermes — not that a Cursor IDE
session looks right.

1. Rebuild + `uv run --frozen tools/validate.py` (exit 0) — always.
2. Install-relevant: `hermes plugins doctor` against the **installed dist
   package** (`hermes plugins doctor pstack --ci`, run from outside the
   repo — `pstack` resolves to the installed plugin id) or against the
   **branch-local build** (`hermes plugins doctor "$PWD/pstack" --ci`, run
   from the repo root — explicit path so it does not silently hit the
   installed dist).
3. Optional smoke: load `poteto-mode` via the invoke route in
   [docs/USING.md](docs/USING.md) (`skill_view` or `skills.external_dirs`) and
   run one real task. Failures with a stock package and clean doctor → hermes
   harness / routing issue, not a silent skill rewrite.

Do not treat Cursor dual-load, Graphite, or Cursor-only agent tools as the
verification surface for this port.

## Hermes vocabulary (use these; ban the aliases)

When writing or editing converter output, docs, or tooling, speak **hermes**.
CI scans every decodable package file (`tools/bans.py` +
`HERMES_ADAPTATION_BANS` in `tools/validate.py`). Rationale:
[docs/ADAPTATIONS.md](docs/ADAPTATIONS.md) §2.

| Use on hermes | Banned / upstream alias (do not ship) |
|---|---|
| `delegate_task` (persona in the task prompt; background as hermes supports) | `Task` / `subagent_type` / `run_in_background` / `environment: "cloud"` |
| `clarify` | `AskQuestion` |
| `session_search` (hermes session store) | `agent-transcripts/*.jsonl` paths |
| recurring `hermes cron` wake | terminal `/loop` as the prescribed mechanism |
| `goal.md` beside the plan in the agent store | armed Cursor `/goal` as the mechanism |
| `hermesbot` (`hermes send` / `hermes peer` / gateway webhook) | `grokbot` / `make-bot-ui` / Tailscale bot |
| hermes `skill_manage` | Cursor `create-skill` |
| `config/models.json` ← `tools/assets/model-panel.json` | hand-tuned shipped panel only |

Cursor still appears in three **legitimate** roles only — preserve, do not
"fix":

1. **Upstream pin** — `cursor/plugins` @ `93b00b8` (MIT © Lauren Tan); homepage
   / repo URLs; attribution lines.
2. **Inert dual-load** — `pstack/.cursor-plugin/`, `pstack/agents/` (hermes
   probes the root manifest only).
3. **Bug routing** — upstream-only bugs → `cursor/plugins`; hermes defects →
   `NousResearch/hermes-agent`; port issues → this repo.

## Hard rules (CI enforces)

- **Pin lock-step.** `UPSTREAM_PIN`
  (`93b00b89ef425a9c1bac0d0b317dfc49c930ac99`) is declared in `ci.yml`,
  `release.yml`, and `upstream-drift-watch.yml` — all three move together.
  Procedure: [docs/RUNBOOK-upstream-drift.md](docs/RUNBOOK-upstream-drift.md).
- **Anchors audited.** A converter transform whose anchor matches nothing in
  the upstream build fails loudly. Re-anchor or prune; never silence the audit.
- **Two version lines.** Package keeps upstream identity `0.14.8`; repo
  releases are `v0.4.x` in `CHANGELOG.md`. Never mix them.
- **Encoding.** LF-only, no BOM, UTF-8 (`.gitattributes` + `validate.py`).
- **Converter changes are documented.** New pass/map → ADAPTATIONS row with
  reviewer check + rebuilt `pstack/` in the same PR.
- **Excluded upstreams stay excluded.** `automations/benny` and
  `skills/make-bot-ui` omitted (slot filled by repo-owned `hermesbot`).
- **Dist repo is build output.** `iap/pstack` is written only by CI
  (`publish-plugin.yml`), append-only. Never hand-push. Never point install
  docs at this dev repo's root (scanner sees `tools/` ban needles).

## Common traps

- Editing `pstack/skills/hermesbot/SKILL.md` — edit
  `tools/assets/hermesbot/SKILL.md` and rebuild.
- Hand-tuning `pstack/config/models.json` — edit
  `tools/assets/model-panel.json` and rebuild; `validate.py` checks they match.
- "Fixing" Cursor mentions that are attribution or dual-load — correct as-is.
- Rewriting hermes primitives back into Cursor vocabulary — bans catch this.
- Blurring install routes: **root** (`hermes plugins install iap/pstack`) keeps
  `.git` and updates via `hermes plugins update pstack`; **subdir**
  (`iap/pstack-hermes/pstack`) strips `.git` → reinstall only. Docs must keep
  them distinct.
- Using Cursor/Graphite tooling habits as the implementation or review path
  for hermes delivery — verify with convert → validate → doctor / hermes invoke.
- Pointing hermes `skill_manage` / `hermes learning` / self-evolution at
  stock package skills — personal improvements belong in a skill tap or dist
  fork; durable package changes go through the converter
  (see [docs/USING.md](docs/USING.md)).
