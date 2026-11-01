# AGENTS.md

Always-on operating contract for AI agents working **in this repository**.
Keep this file short. Deep ops: open one row in
[docs/agent/](docs/agent/README.md) — do not load the whole tree every turn.

| Need | Go |
|---|---|
| End-user invoke / customize | [docs/USING.md](docs/USING.md) |
| Human setup, Actions, PR, release | [CONTRIBUTING.md](CONTRIBUTING.md) |
| Adaptation ledger | [#94](https://github.com/iap/pstack-hermes/issues/94) |

> [!IMPORTANT]
> **pstack-hermes** ports Cursor *pstack* to **Hermes**
> (`NousResearch/hermes-agent`). Runtime target is hermes. Cursor is upstream
> attribution, not the delivery or verify path.

CONTRIBUTING wins on **what to write** (authoring/release). This file wins on
**how to work in the repo**.

## The one rule

> [!WARNING]
> **Never hand-edit generated package surfaces.** Change `tools/` /
> `tools/assets/`, rebuild with `tools/convert.py`, validate. Paths:
> [docs/agent/layout.md](docs/agent/layout.md). Provenance:
> `.build-provenance.txt`.

## Where a change goes

| If you need to… | Do this |
|---|---|
| Change skill prose, maps, hermesbot, model panel, bans | `tools/` / `tools/assets/` → rebuild → validate → adaptation issue if converter-shaped ([#94](https://github.com/iap/pstack-hermes/issues/94)) |
| Personal / project procedures | Local skills, skill tap, or fork — not stock plugin `SKILL.md` ([USING](docs/USING.md)) |
| Doctor clean but stock install misbehaves on hermes | Fix in `NousResearch/hermes-agent`; `patches/` is historical only |
| Bug on upstream Cursor pstack without this port | `cursor/plugins` ([SECURITY.md](SECURITY.md)) |
| Touch `agents/`, re-add `benny` / `make-bot-ui` | Leave as-is (scanner contract) |
| GitLab / `glab` stack support | Halted |
| CI / pins / workflow policy | [CONTRIBUTING](CONTRIBUTING.md#github-actions--workflow-policy); `tools/check_pins.py` |
| Agent deep-ops prose | [docs/agent/](docs/agent/README.md) |

**Stack forge:** Graphite (`gt`) → GitHub (`gh`) fallback → GitLab halted.

## Before you claim done

Follow the work loop in
[docs/agent/convert-adapt.md](docs/agent/convert-adapt.md). Say `not run` with
cause when a gate needs hermes/network you lack. PRs that change generated
surfaces: `rebuilt from pin <sha>` + name the converter change.

## Hard contracts

| Contract | Owner |
|---|---|
| Generated surfaces never hand-edited | reproducibility gate; [layout](docs/agent/layout.md) |
| Converter-shaped changes get adaptation + reviewer check | [#94](https://github.com/iap/pstack-hermes/issues/94); [convert-adapt](docs/agent/convert-adapt.md) |
| Hermes vocabulary in shipped text | `tools/bans.py`, `validate.py` |
| `UPSTREAM_PIN` lock-step | `tools/check_pins.py`; [upstream-drift](docs/agent/upstream-drift.md) |
| Action pins via Dependabot | `.github/dependabot.yml` |
| LF-only, no BOM, UTF-8 | `.gitattributes`, `validate.py` |
| `master` + append-only `dist` | CI publish |
| Repo `v0.5.x` / package `0.15.5` | CHANGELOG / CONTRIBUTING |
| Planning in GitHub issues only | not under `docs/` |
| Bot threads: evidence reply; no resolver | [review-ops](docs/agent/review-ops.md) |

## Traps

> [!WARNING]
> Cursor dual-load is not the verify path — convert → validate → doctor /
> hermes invoke.

> [!WARNING]
> Do not point `skill_manage` at stock `agent-plugin-pstack-…` skills.

> [!WARNING]
> Do not "fix" Cursor attribution that is dual-load/provenance, or rewrite
> hermes primitives into Cursor vocabulary.

> [!NOTE]
> Doctor target `pstack` is ambiguous from this repo root — use `"$PWD"` for
> the branch tree. Shorthand `iap/pstack`: [#100](https://github.com/iap/pstack-hermes/issues/100).
