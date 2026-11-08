---
name: hermes-vocabulary
description: >-
  Use when a coworker or harness message uses Cursor terms and you must answer
  with hermes terms (delegate_task, clarify, hermes cron, goal.md, skill_manage).
  Disambiguates Hermes agent vocabulary before delegating.
---

# Hermes vocabulary

> [!WARNING]
> `docs/hermes-vocabulary.md` is the single mapping home. Update that file
> first, then this skill and `tools/bans.py`.

## Canonical mapping

Exact alias tokens live in `docs/hermes-vocabulary.md` (not spelled here).
The hermes side (left column) is what you must *say*; the Cursor side is
described, not quoted, so this file itself stays ban-clean.

| Use this (hermes) | Banned alias (Cursor, described) |
|---|---|
| `delegate_task` | backticked Cursor task type / subagent selector / general-purpose subagent |
| `delegate_task` (background) | background-run flag |
| local execution (no cloud worker) | cloud environment selector |
| `clarify` | Ask-style question harness |
| `session_search` | transcripts directory alias |
| `hermes cron` wake | terminal `/loop` |
| `goal.md` in agent store | armed Cursor `/goal` |
| `hermesbot` | `grokbot` / `make-bot-ui` / Tailscale bot |
| `skill_manage` (local/tap only) | Cursor skill-creation primitive |
| panel from `config/models.json` | hand-tuned shipped panel file |

Tool names: `search_files` for `Glob`/`Grep`, `read_file` for `Read`.

## How to use

Load this skill *before* translating a request. Answer in the left-hand column only; if the user’s term matches the right-hand description, correct it once and use the hermes term for the rest of the turn.

## Guardrails

- Keep this table mirrored with `docs/hermes-vocabulary.md` and `tools/bans.py`. A mapping that exists only in one place is not a contract.
- Short alias swaps inside a paragraph are always safe; expanding a forbidden alias into a sentence is not.
