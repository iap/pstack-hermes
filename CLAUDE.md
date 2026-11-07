@AGENTS.md

## Claude Code notes

- Before editing any file, check the "Where to edit" table in AGENTS.md. If the
  path is generated (root `skills/`, `config/`, `assets/`, `README.md`,
  `plugin.json`, `LICENSE`, `.build-provenance.txt`), stop and change
  `tools/` or `tools/assets/` instead, then rebuild.
- Never run a rebuild without first confirming the upstream clone is at the
  SHA declared in `UPSTREAM_PIN`. The only exception is a re-pin, which follows
  the step order in `docs/agent/upstream-drift.md`.
- Run the full Verify block from AGENTS.md before saying a task is done.
  If `bun` or `hermes` is unavailable locally, say so explicitly and name which
  checks you skipped. Do not claim they passed.
- Keep diffs scoped to the task. Put out-of-scope findings in an issue
  rather than fixing them in the same change.
- Never push, force-push, retag, or touch the `dist` branch unless asked.
- Don't paste webhook secrets, signatures, or tokens into commits, issues or PR text.
- If AGENTS.md and README.md disagree, trust AGENTS.md and flag the discrepancy
  in your summary rather than silently picking one.
