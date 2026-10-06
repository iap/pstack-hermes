# AGENTS.md

> [!IMPORTANT]
> This repository is **pstack-hermes** — the unofficial community port of
> Cursor's *pstack* agent-method plugin to the **Hermes Agent** platform
> (`NousResearch/hermes-agent`). The runtime target is **hermes**. Cursor is
> upstream attribution and an inert dual-load surface only — not the delivery
> path. Do not invent Cursor IDE or Cursor-plugin authoring workflows to
> implement or verify this package. Stack tooling follows the policy below
> (Graphite default, GitHub fallback) — that is product behavior, not a
> Cursor-only verify path.

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

## Stock skills vs Hermes self-improvement (hard gap)

Hermes can improve procedural memory via `skill_manage`, `/learn`, and the
background learning loop. That loop writes **profile-local** skills under
`~/.hermes/skills/` (or a skill tap). It must **not** be treated as the path
to improve **stock** pstack skills shipped in this package.

| Intent | Path | Survives `hermes plugins update`? |
|---|---|---|
| Change stock method for all users | Converter / `tools/assets/` → rebuild → validate → release | Yes (product) |
| Personal or project procedure | `skill_manage` / `/learn` into **local** `~/.hermes/skills/` | Yes (outside package) |
| Owned variant of pstack skills | **Fork** of this repo, install from the fork's `pstack/` subdir | Yes (you control merge) |
| New skills beside pstack | **Skill tap** (`hermes skills tap add` / install) | Yes |
| Durable "learning" into installed plugin `SKILL.md` files | **Forbidden** as source of truth | No — reinstalls overwrite the installed tree |

> [!WARNING]
> Never instruct `skill_manage` (or any self-evolution path) to patch
> **namespaced plugin skills** (`agent-plugin-pstack-…`) as the durable home
> for improvements. Stock package text changes only through the converter and
> a published release. In-place edits of the installed tree are temporary at
> best (see [docs/USING.md](docs/USING.md)).

When writing converter output or docs: hermes `skill_manage` replaces Cursor
`create-skill` for *authoring* — it does not authorize mutating stock plugin
skills in place.

## Stack forge policy (product)

Orchestration / frontier discovery follows this freeze (do not invert):

| Provider | Status |
|---|---|
| **Graphite (`gt`)** | **Default** when available |
| **GitHub (`gh`)** | **Fallback** (PR base/head topology; explicit `github` or auto fallback) |
| **GitLab (`glab`)** | **Halted** — reserved in wording only; do not implement in active milestones |

Do not open implementation work for `glab` or treat missing Graphite as a
hard failure when GitHub fallback can satisfy the task. Restacks and some
stack surgery may still require Graphite; document incomplete verdicts rather
than inventing a second stacker.

## Change triage (30 seconds)

Default home for work is **this repo**. Escalate only when the table says so.

| If you need to… | Do this | Not this |
|---|---|---|
| Change skill prose, delegation wording, model panel, hermesbot, bans, docs, converter maps | Edit `tools/` / `tools/assets/` → rebuild → validate → (ledger row if converter changed) | Hand-edit `pstack/`; rewrite in Cursor vocabulary |
| Personal skill improvement or new procedures | Local skills, skill tap, or fork of this repo ([docs/USING.md](docs/USING.md)) | `skill_manage` against stock plugin skills; durable edits under the install tree |
| Package validates / doctor is clean, but stock install misbehaves on hermes | File/fix in `NousResearch/hermes-agent`; `patches/` is **historical reference only** ([docs/PATCHES.md](docs/PATCHES.md)) | Paper over harness gaps with skill prose that claims nonexistent tools |
| Bug reproduces on upstream Cursor pstack *without* this port | Route to `cursor/plugins` ([SECURITY.md](SECURITY.md)) | "Fix" it in the converter as if it were a port bug |
| Touch `.cursor-plugin/`, `pstack/agents/`, attribution, excluded `benny` / `make-bot-ui` | Leave as-is (dual-load / scanner contract) | "Clean up", re-add, or modernize |
| GitLab / `glab` stack support | Leave halted; no implementation | Add provider code or active milestone work |

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
| `.github/` | CI, labeler, issue templates | pin SHA must stay in lock-step across workflows (enforced: `tools/check_pins.py`); workflow edits must pass actionlint and `tools/check_action_shell.py`; action pins are bumped by dependabot, not by hand |
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

Do not treat Cursor dual-load or Cursor-only agent tools as the verification
surface for this port. Stack provider behavior is product policy (Graphite
default / GitHub fallback), not a substitute for convert → validate → doctor.

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
| hermes `skill_manage` (local / tap skills — not stock plugin mutation) | Cursor `create-skill` |
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
  (`c47b12849e43f18d5c374c7069c744cc55b0ea00`) is declared in `ci.yml`,
  `release.yml`, and `upstream-drift-watch.yml` — all three move together. The build steps that consume it are shared via
  `.github/actions/build-package`.
  Procedure: [docs/RUNBOOK-upstream-drift.md](docs/RUNBOOK-upstream-drift.md).
- **Anchors audited.** A converter transform whose anchor matches nothing in
  the upstream build fails loudly. Re-anchor or prune; never silence the audit.
- **Two version lines.** Package keeps upstream identity `0.15.5`; repo
  releases are `v0.4.x` in `CHANGELOG.md`. Never mix them.
- **Encoding.** LF-only, no BOM, UTF-8 (`.gitattributes` + `validate.py`).
- **Converter changes are documented.** New pass/map → ADAPTATIONS row with
  reviewer check + rebuilt `pstack/` in the same PR.
- **Excluded upstreams stay excluded.** `automations/benny` and
  `skills/make-bot-ui` omitted (slot filled by repo-owned `hermesbot`).
- **Single-source installs.** Installs come from this repo's `pstack/` subdir
  (`hermes plugins install iap/pstack-hermes/pstack`). The old dist repo
  `iap/pstack` is retired — never publish there again; never document a
  root install of this dev repo (scanner sees `tools/` ban needles).

## Common traps

- Editing `pstack/skills/hermesbot/SKILL.md` — edit
  `tools/assets/hermesbot/SKILL.md` and rebuild.
- Hand-tuning `pstack/config/models.json` — edit
  `tools/assets/model-panel.json` and rebuild; `validate.py` checks they match.
- "Fixing" Cursor mentions that are attribution or dual-load — correct as-is.
- Rewriting hermes primitives back into Cursor vocabulary — bans catch this.
- Install-update mechanics: subdir installs strip `.git` (hermes design), so
  `hermes plugins update` does NOT work for them — updates are reinstalls
  (`hermes plugins install iap/pstack-hermes/pstack --force`). Docs must say so.
- Using Cursor IDE dual-load habits as the implementation or review path for
  hermes delivery — verify with convert → validate → doctor / hermes invoke.
- Pointing hermes `skill_manage` / learning / self-evolution at **stock**
  package skills — personal improvements belong in local skills, a skill tap,
  or a dist fork; durable package changes go through the converter
  (see [docs/USING.md](docs/USING.md)).
- Implementing GitLab (`glab`) or treating it as an active milestone — halted.
