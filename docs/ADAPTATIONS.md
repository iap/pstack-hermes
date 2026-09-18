# Adaptations ledger

> [!IMPORTANT]
> This document describes **the port's contract** — what was changed, why, and
> how a reviewer verifies it. It deliberately does **not** restate the method;
> the skills are the single source of truth for that, and the machine-generated
> fix register in `pstack/.build-provenance.txt` is the single source of truth
> for what a given build actually did. Every row here must be traceable to a
> converter map, a validator check, or the pinned upstream SHA.

- Upstream: `cursor/plugins` → `pstack`, pinned at `93b00b8` (MIT © Lauren Tan).
- Package: `pstack/` — **generated** by `tools/convert.py`; never hand-edited.
- A new conversion pass **must add a row here** (see Maintenance at the bottom).

## Terminology — the "Phase-N" labels

`Phase-0`, `Phase-1`, `Phase-2A`, `Phase-4` are **historical stage labels from
the original port project**, embedded in the converter's docstring and in the
generated `.build-provenance.txt` fix register. They are names of
port-work stages, not runtime concepts — the shipped plugin and hermes attach
no meaning to them. For anyone reading the provenance file or converter:

| Label | What it named |
|---|---|
| Phase-0 | The initial conversion stage: copy the pinned upstream tree into the hermes `agent-plugins-v1` package shape (root manifest injection, skills flattening, UTF-8/LF normalization, provenance writing). The converter is still "the Phase-0 converter" because every build replays exactly that stage. |
| Phase-1 | Post-copy hygiene transforms (R1, F16, F10–F12, F-publish in the pass table below). |
| Phase-2 / Phase-2A | The vocabulary-adaptation waves: delegation translation (`Phase-2A` in the fix register) and related Cursor→hermes rewording passes. |
| Phase-4 | The *future* rebuild of the two scanner-excluded upstream components (`automations/benny`) as hermes-native mechanisms — a label for "not done, deliberately excluded", not a scheduled milestone. |

References in the converter docstring to a "study" (Ch3, subagent_03a) cite
the original port's internal research notes; those notes are **not** part of
this repository. The authoritative contract is this ledger plus the converter
code itself.

## 1. Conversion passes

Each pass is an ordered anchor map or code transform in `tools/convert.py`.
Anchors are audited: a pass whose anchor matches nothing **fails the build**
(upstream drift must be resolved in the map, never ignored).

| Pass | What it changes | Source of truth | Reviewer check |
|---|---|---|---|
| frontmatter fix | `skills/poteto-mode/SKILL.md` frontmatter name `Poteto Mode` → `poteto-mode` | `FRONTMATTER_FIXES` | validate: every skill name == its dir, kebab-case |
| R1 | poteto-mode principles index regenerated from the 21 `principle-*` leaves | `build_principles_index()` | validate: "principles index == leaf-generated" |
| F16 | `check-plan.mjs` fast-lane slug from `PSTACK_FAST_LANE`; multi-phase-plan documents the override | phase-1 transforms | validate: F16 check |
| F10–F12 | `worktree-audit.sh` portable (GNU/BSD `stat`/`date` helpers); space-safe awk | phase-1 transforms | validate: F10–F12 check |
| F-publish | 3 localhost endpoint literals in the feature-map example neutralized (install-scanner network findings). Pass is commented `T5` in the converter but **registered as `F-publish`** — match the register | phase-1 transforms | validate: banned-construct scan |
| T8 | factual fixes from the deep review (readonly-MCP rationale, swarm params, tool names, model-panel path, principle cross-link) + source-playbook note | `T8_MAP` | validate: T8 check |
| T9/T10 | hermes-native discovery (`session_search`) in why/reflect/recall; `setup-pstack` writes `config/models.json` | `T9_MAP`, `T10_MAP` | validate: T9 + T10 checks |
| Stage-D | `config/models.json` shipped with the repo model panel (18 roles) | `tools/assets/model-panel.json` | validate: panel == repo panel |
| T11 | hardcoded paths (`.cursor` rules/projects/skills, `agent-transcripts`, `/tmp` scratch dirs) → hermes equivalents | `T11_MAP` | anchor audit + T11 scope test |
| T12 | Cursor built-in `/loop` → gateway cron wake; `/goal` → `goal.md` in the agent store | `T12_MAP`, `T12_SCRIPT_MAP` | anchor audit; zero `/loop`/`goal` leftovers; `check-plan.mjs` marker |
| T13 | residual vendor coupling (`cursor-team-kit`, `deslop`, cloud-agent fleet, Graphite `gt`) reworded | `T13_MAP` | anchor audit; **zero `cursor-team-kit`** in shipped skills |
| Phase-2A | delegation vocabulary: `Task`/`subagent_type`/`AskQuestion`/`run_in_background`/`environment: "cloud"` → `delegate_task`/`clarify`/background execution | `DELEGATION_MAP` | validate: "no Cursor delegation tokens" |
| G1 | delegation escape hatch (in-thread authoring for resident surgical edits, with mandatory independent delegate review) | G1 transform | validate: G1 check |
| F-publish | `automations/benny` + `skills/make-bot-ui` excluded (install-scanner verdicts); the make-bot-ui slot filled by the repo-owned `skills/hermesbot` | converter flow + `tools/assets/hermesbot/SKILL.md` | validate: both exclusions + skill count 45 |
| manifest | root `plugin.json` injected (agent-plugins-v1 `$schema`, 9 whitelisted fields) | converter flow | validate gold manifest: real loader, zero diagnostics |
| assets | `assets/` (the Cursor manifest's referenced asset, 1 file) copied verbatim | converter flow + manifest-asset check | gold manifest: referenced asset resolves; build fails if it is missing |
| README | package README generated (differences contract + Known limitations) from the live fix register | README template in `convert.py` | `validate.py` (present) + gold load |

## 2. Primitive mapping (what stands in for what)

| Cursor / upstream primitive | Hermes treatment | Status |
|---|---|---|
| `Task` subagents with `subagent_type` | `delegate_task` (role `leaf`), persona via the task prompt | native |
| `AskQuestion` | `clarify` | native |
| transcript files (`agent-transcripts/*.jsonl`) | `session_search` over the hermes session store | native |
| Cursor `create-skill` | hermes skill-authoring (`skill_manage`) | native |
| MCP discovery (`available-tools` map, `mcps/`) | the session's configured MCP tool catalog (no `mcp.json` shipped) | native, config-dependent |
| terminal `/loop` (sleep + wake sentinel) | recurring `hermes cron` job whose delivery re-wakes the session | approximated |
| armed `/goal` | `goal.md` beside the plan in the agent store, re-read each wake | approximated |
| `grokbot` / `make-bot-ui` (Grok Bot routines, Tailscale) | `hermesbot` (gateway webhook + `hermes send` + `hermes peer`) | replaced |
| `cursor-team-kit` skills (`deslop`, `control-ui`, `control-cli`) | named directly; **external prerequisites**, not shipped | absent, documented |
| Graphite (`gt`) stacker for frontier discovery | `orch frontier set` now supports provider selection: `auto`, `graphite`, and GitHub-native PR base/head topology; GitLab is reserved but not implemented yet | partially native |
| Cursor worktree isolation per subagent | the skills manage worktrees themselves | approximated |

## 3. Deliberately not ported

| Upstream artifact | Why not |
|---|---|
| `automations/benny` | install-scanner persistence verdict (copy-instructions) — Phase-4 rebuild would be a cron/loop job; excluded today |
| `skills/make-bot-ui` | install-scanner privilege verdict (remote-installer pattern) + deepest vendor coupling; replaced by `hermesbot` |
| `docs/guide/` | upstream's human-facing tutorial; outside the plugin payload and not a port maintenance surface |
| `.cursor-plugin/`, `agents/` | inert on hermes; preserved only so the same tree still loads as a Cursor plugin *structurally* |

## Maintenance

- Adding or changing a pass in `tools/convert.py` requires a matching row here.
  The pass list above mirrors `st.fixes` and the audited map registry.
- A row without a **reviewer check** is a claim, not documentation — don't add one.
- Nothing in this file may paraphrase skill content. Link to the skill instead.
