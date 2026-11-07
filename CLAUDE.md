@AGENTS.md

## Claude Code notes

- Before editing any file, check the "Where to edit" table in AGENTS.md.
  The package surfaces (`plugin.json`, `skills/`, `config/`, `assets/`,
  `README.md`, `LICENSE`) are hand-written source — edit them directly.
  There is no converter, rebuild, or upstream pin (#156).
- Run the full Verify block from AGENTS.md before saying a task is done.
  If `bun` or `hermes` is unavailable locally, say so explicitly and name which
  checks you skipped. Do not claim they passed.
- Keep diffs scoped to the task. Put out-of-scope findings in an issue
  rather than fixing them in the same change.
- Never push, force-push, retag, or touch the `dist` branch unless asked.
- Don't paste webhook secrets, signatures, or tokens into commits, issues or PR text.
- If AGENTS.md and README.md disagree, trust AGENTS.md and flag the discrepancy
  in your summary rather than silently picking one.
