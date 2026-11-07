# Adapt and verify (standalone)

Single home for changing the package. Layout paths:
[layout.md](layout.md). Standalone decisions:
[standalone-decisions.md](../standalone-decisions.md). The upstream
converter (`tools/convert.py`) was retired in #156; there is no rebuild
or re-pin step. Full instruction audit: #159.

## Work loop

```sh
uv sync
# 1. Edit the package surfaces directly (plugin.json, skills/, config/,
#    assets/, README.md, LICENSE), plus tools/, docs/, …
# 2. Must exit 0:
uv run --frozen tools/validate.py
uv run --frozen pytest -q
uv run --frozen ruff check tools
uv run --frozen python tools/check_docs.py
```

Then:

1. Package-shaped → [Verify](#verify).
2. Scope changes → link the tracking issue (#156 sub-issues; docs audit
   #159, poteto extraction #158).

Poteto checkers: see [CONTRIBUTING Setup](../../CONTRIBUTING.md#setup)
(`bun run test` / `typecheck` under `skills/poteto-mode/scripts`;
root `scripts/` after #158 lands).

## Hermes vocabulary

Speak **hermes** in package output, docs, and tooling. Enforced by
`tools/bans.py` + `HERMES_ADAPTATION_BANS` in `validate.py`.
Single mapping home: [hermes-vocabulary.md](../hermes-vocabulary.md).

| Use | Banned alias |
|---|---|
| `delegate_task` | `Task` / `subagent_type` / `run_in_background` / `environment: "cloud"` |
| `clarify` | `AskQuestion` |
| `session_search` | `agent-transcripts/*.jsonl` |
| `hermes cron` wake | terminal `/loop` as the mechanism |
| `goal.md` in agent store | armed Cursor `/goal` |
| `hermesbot` | `grokbot` / `make-bot-ui` / Tailscale bot |
| `skill_manage` (local/tap only) | Cursor `create-skill`; never stock plugin mutation |
| panel ← `tools/assets/model-panel.json` | hand-tuned shipped `config/models.json` |

## Verify

Prove the **built package** on hermes — not Cursor IDE dual-load.

1. `validate.py` on the edited tree — always.
2. Doctor: branch `hermes plugins doctor "$PWD" --ci`; installed
   `hermes plugins doctor pstack --ci` **outside** this repo.
3. Optional: load `poteto-mode` per [USING.md](../USING.md). Clean doctor +
   stock package failure → hermes harness issue, not a silent skill rewrite.
4. Publish (CI): `master` maintains append-only `dist`.

Validate runs static → repo YAML → gold manifest → gold load, including
the hermes adaptation contract and model-panel consistency.
