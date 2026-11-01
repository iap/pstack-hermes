<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:5a9bb58123eed2229ab514f3ae50284af772275f506e0c1efa0ff6cc825a33df -->

<!-- coderabbit-ai-generated-section:v1:8f2748e92563f87c7ee659be543052bba4f28235ed4f49943c12c3a57b13902a -->

<!-- coderabbit-ai-generated-section:v1:1f1ca519bebada9545e7979d5b65d9f357c0116b183de942d6bb1de830becd56 -->

<!-- coderabbit-ai-generated-section:v1:102e84b05f8d8d4a44ae4ee9afe2278bd719d3e5d51f2ca6cb79940eafd85b8c -->

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
[adaptation register](https://github.com/iap/pstack-hermes/issues/94).

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
| Owned variant of pstack skills | **Fork** of this repo, install from the fork | Yes (you control merge) |
| New skills beside pstack | **Skill tap** (`hermes skills tap add` / install) | Yes |
| Durable "learning" into installed plugin `SKILL.md` files | **Forbidden** as source of truth | No — `dist` publishes overwrite the installed tree |

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
| Change skill prose, delegation wording, model panel, hermesbot, bans, docs, converter maps | Edit `tools/` / `tools/assets/` → rebuild → validate → (adaptation issue if converter changed) | Hand-edit `pstack/`; rewrite in Cursor vocabulary |
| Personal skill improvement or new procedures | Local skills, skill tap, or fork of this repo ([docs/USING.md](docs/USING.md)) | `skill_manage` against stock plugin skills; durable edits under the install tree |
| Package validates / doctor is clean, but stock install misbehaves on hermes | File/fix in `NousResearch/hermes-agent`; `patches/` is **historical reference only** ([docs/PATCHES.md](docs/PATCHES.md)) | Paper over harness gaps with skill prose that claims nonexistent tools |
| Bug reproduces on upstream Cursor pstack *without* this port | Route to `cursor/plugins` ([SECURITY.md](SECURITY.md)) | "Fix" it in the converter as if it were a port bug |
| Touch `agents/`, attribution, excluded `benny` / `make-bot-ui` | Leave as-is (scanner contract) | "Clean up", re-add, or modernize |
| GitLab / `glab` stack support | Leave halted; no implementation | Add provider code or active milestone work |

## Default work loop

```sh
uv sync
# 1. Edit the hand-written source of truth (tools/, tools/assets/, docs/, …)
# 2. Rebuild from a clone at the pinned upstream SHA:
uv run --frozen tools/convert.py --source <pstack-clone>
# 3. Must exit 0:
uv run --frozen tools/validate.py
uv run --frozen pytest -q
uv run --frozen ruff check tools
```

Then:

1. If the converter/maps/assets that shape the package changed → create an adaptation issue linked to the
   [preserved register](https://github.com/iap/pstack-hermes/issues/94) with a **reviewer check**, and
   include rebuilt `pstack/` in the same PR (`rebuilt from pin <sha>` in the body).
2. If the change is **install-relevant** (manifest, skill discovery, package
   layout) → `hermes plugins doctor` against the **installed dist package**
   (`hermes plugins doctor pstack --ci`, run from outside the repo — `pstack`
   resolves to the installed plugin id) or against the **branch-local build**
   (`hermes plugins doctor "$PWD/pstack" --ci`, run from the repo root —
   explicit path so it does not silently hit the installed dist).
3. Re-pin upstream only via
   [docs/agent/upstream-drift.md](docs/agent/upstream-drift.md) — never by
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
| `agents/` | generated; inert on hermes | agent personas; leave as-is |
| `tools/` | hand-written converter, validator, bans, scanner gate, tests | source of package truth |
| `tools/assets/` | inputs the converter copies in (`model-panel.json`, `hermesbot/SKILL.md`) | edit here, then rebuild |
| `docs/` | maintained instructions: usage, development, operations | plans and adaptations belong in GitHub issues |
| `patches/` | historical hermes-fork patch reference | not required to load/install; see PATCHES.md |
| `.github/` | CI, labeler, issue templates | pin SHA must stay in lock-step across workflows (enforced: `tools/check_pins.py`); workflow edits must pass actionlint, `tools/check_action_shell.py` and `tools/check_action_inputs.py`; action pins are bumped by dependabot (workflows and each composite action have their own entry), not by hand |
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
[adaptation register](https://github.com/iap/pstack-hermes/issues/94) §2.

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

## Hard rules (CI enforces)

- **Encoding.** LF-only, no BOM, UTF-8 (`.gitattributes` + `validate.py`).
- **`master` is the intended default development branch.**
- **Repo releases** are `v0.5.x` in `CHANGELOG.md`. Package keeps upstream
  identity `0.15.5`.
  this migration merges. `dist` remains CI-owned append-only compatibility
  output. Never rewrite or delete it while installed clones depend on it.
- **GitHub owns planning.** Proposals, adaptation records, reviewer checks and
  delivery plans live in issues, native sub-issues and milestones. `docs/`
  contains maintained instructions, not parallel task state.

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:20bac8af517d82fdb234c1320f75a1dba0278db5aa0318bf9a41ccdb7a3e6aec -->

## Identity and installation goal

The project and plugin are named `pstack`. The canonical GitHub repository
and project slug are `iap/pstack-hermes` and `pstack-hermes`, respectively.
Keep the current GitHub URL; do not create or rename a repository to provide an
install alias.

The desired command is `hermes plugins install iap/pstack --enable` from this
repository. Current Hermes interprets it as GitHub repo `iap/pstack`; it is
not a catalog alias for this project. [Issue #100](https://github.com/iap/pstack-hermes/issues/100)
tracks making the exact command work without a second repository. Keep the
verified current-repository install paths documented until that is proven on
a released Hermes version. Check the current default branch before choosing a
root or `pstack/` subdirectory install; pin and update behavior differ.

## Bot review findings

- Inspect each finding against the pre-change contract, current code, callers,
  tests and the current review thread. Check whether it is already fixed,
  duplicated, outdated, incorrect or blocked before changing behavior.
- For a valid finding, implement the compatible fix and run the relevant
  checks. If it conflicts with the contract or needs a decision, explain the
  conflict and seek the necessary clarification; do not weaken a contract to
  satisfy a bot.
- Reply in the same bot review thread with what changed and why, the commit or
  code reference and verification results, including blocked checks. For a
  false positive, duplicate or already-fixed finding, reply with evidence and
  explain why no further change is needed. Report any unresolved blocker.
- Do not mark bot review threads resolved with the resolver. A maintainer can
  decide the thread status after reading the reply. If a reply cannot be sent,
  report that limitation rather than claiming it was posted.

## Common traps

<!-- /coderabbit-ai-generated:v1 -->

- Editing `pstack/skills/hermesbot/SKILL.md` — edit
  `tools/assets/hermesbot/SKILL.md` and rebuild.
- Hand-tuning `pstack/config/models.json` — edit
  `tools/assets/model-panel.json` and rebuild; `validate.py` checks they match.
- "Fixing" Cursor mentions that are attribution or dual-load — correct as-is.
- Rewriting hermes primitives back into Cursor vocabulary — bans catch this.
<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:e369cdcbba20d961295a45ff0b75f01d9fd59605c87bb236b0f8637dba1acad1 -->

- Install-update mechanics: unpinned `dist` root installs update through Git;
  current Hermes re-clones tracked unpinned `master` subdirectory installs.
  Both use `hermes plugins update pstack`. Older installs without recorded
  source need recovery; pinned installs need an explicit new SHA and `--force`.

<!-- /coderabbit-ai-generated:v1 -->
- Using Cursor IDE dual-load habits as the implementation or review path for
  hermes delivery — verify with convert → validate → doctor / hermes invoke.
- Pointing hermes `skill_manage` / learning / self-evolution at **stock**
  package skills — personal improvements belong in local skills, a skill tap,
  or a dist fork; durable package changes go through the converter
  (see [docs/USING.md](docs/USING.md)).
- Implementing GitLab (`glab`) or treating it as an active milestone — halted.


<!-- /coderabbit-ai-generated:v1 -->