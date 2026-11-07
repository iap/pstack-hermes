# Hermes vocabulary (issue #157)

Single mapping home for every Cursor-to-hermes vocabulary pair this package enforces. All other references point here.

> [!WARNING]
> Update this file first, then propagate to the enforcement points below. A mapping that exists only in a skill, or a banned word that exists only in a doc, is not a contract.

## Canonical mapping

| Use this (hermes) | Banned alias (Cursor) |
|---|---|
| `delegate_task` | `` `Task` `` / `subagent_type` / `generalPurpose` |
| `delegate_task` (background) | `run_in_background` |
| local execution (no cloud worker) | `environment: "cloud"` |
| `clarify` | `AskQuestion` |
| `session_search` | `agent-transcripts/*.jsonl` |
| `hermes cron` wake | terminal `/loop` |
| `goal.md` in agent store | armed Cursor `/goal` |
| `hermesbot` | `grokbot` / `make-bot-ui` / Tailscale bot |
| `skill_manage` (local/tap only) | Cursor `create-skill` |
| panel from `tools/assets/model-panel.json` | hand-tuned shipped `config/models.json` |

Tool names: `search_files` for `Glob`/`Grep`, `read_file` for `Read`.

## Enforcement

- `tools/bans.py` `DELEGATION_VOCAB_BANS` — the banned list, shared by `tools/validate.py` and `tools/scanner_gate.py` so the two can never drift. The Cursor transcript alias (`agent-transcripts`) is banned in Markdown only: the shipped `worktree-audit.sh` legitimately mentions that dir for a compatibility check.
- `tools/validate.py` `HERMES_ADAPTATION_BANS` — the broader contract (persona blocks, stale runtime claims, transcript paths, cloud-worker wording, auto selectors).
- Vocabulary gate: `uv run --frozen tools/scanner_gate.py --package . --vocab-only` (0 = clean, 1 = banned vocabulary present, 2 = path error). The flag checks the `DELEGATION_VOCAB_BANS` list and the transcript alias in Markdown only — it does not cover every alias in the table above (e.g. `create-skill`); run `tools/validate.py` for the broader contract checks.

Security bans (`tailscale.com/install.sh`, `FOR_AGENTS.md`, `http://127.0.0.1:4173`) are defined in `tools/bans.py` and are not vocabulary; they are not listed here.

Skill prose that mentions a superseded slug as fallback documentation is intentional and not a violation; the banned constructs are the Cursor runtime words above.
