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

## User-typed aliases

Bare `subagent` and `agent swarm` are user ways of asking for delegation, not banned constructs. Redirect them to `delegate_task` (or the **swarm** skill for fan-out); `skills/hermes-vocabulary` teaches this redirect.

## Enforcement

- `tools/bans.py` `DELEGATION_VOCAB_BANS` — the banned list, shared by `tools/validate.py` and `tools/scanner_gate.py` so the two can never drift. The Cursor transcript alias (`agent-transcripts`) is banned in Markdown only: the shipped `worktree-audit.sh` legitimately mentions that dir for a compatibility check.
- `tools/validate.py` `HERMES_ADAPTATION_BANS` — the broader contract (persona blocks, stale runtime claims, transcript paths, cloud-worker wording, auto selectors).
- Vocabulary gate: `uv run --frozen tools/scanner_gate.py --package . --vocab-only` (0 = clean, 1 = banned vocabulary present, 2 = path error). The flag checks the `DELEGATION_VOCAB_BANS` list and the transcript alias in Markdown only. Bare `subagent` / `agent swarm` stay outside this gate: the banned selector is `subagent_type`, so a user alias redirects (see above) while a Cursor selector is flagged.
- Drift gate: `uv run --frozen python tools/check_docs.py` checks the machine-readable block below against every gate list and against `skills/hermes-vocabulary/SKILL.md`. It covers aliases the `--vocab-only` flag does not (for example `create-skill`, enforced by `tools/validate.py`), and names the file to update when any of them drifts. No checker writes package files.

## Machine-readable enforcement

This block is the canonical list of enforced tokens. Change it here first; the drift gate then tells you which gate list or skill row to update. It is consumed read-only and generates no package surface.

<!-- VOCAB-MAP-BEGIN -->
```json
{
  "version": 1,
  "gates": {
    "tools/bans.py:DELEGATION_VOCAB_BANS": [
      "subagent_type",
      "generalPurpose",
      "AskQuestion",
      "`Task`",
      "run_in_background",
      "environment: \"cloud\""
    ],
    "tools/bans.py:TRANSCRIPT_VOCAB_BANS": ["agent-transcripts"],
    "tools/validate.py:HERMES_ADAPTATION_BANS": [
      "persona:",
      "read-only delegates lose MCP access",
      "Read, Grep, Glob",
      "<ABSOLUTE_PATH>",
      "parallel cloud workers",
      "cloud concurrency limit",
      "`inherit-parent` or `auto`"
    ],
    "tools/validate.py:check_phase1:t9_toks": ["create-skill"]
  }
}
```
<!-- VOCAB-MAP-END -->

Security bans (`tailscale.com/install.sh`, `FOR_AGENTS.md`, `http://127.0.0.1:4173`) are defined in `tools/bans.py` and are not vocabulary; they are not listed here.

Skill prose that mentions a superseded slug as fallback documentation is intentional and not a violation; the banned constructs are the Cursor runtime words above.
