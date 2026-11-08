# Eval harness (#194)

Goal: measure whether the pstack **method** works, not just that files parse.

## Tiers

1. **Deterministic gates** (in CI, every PR): `validate.py`, bans/scanner,
   `check_docs`, dual-lock, dist checkout, pytest, bun (ubuntu + windows).
2. **Behavioral golden tasks** (this directory): fixed prompts per skill,
   rubric-scored `hermes -z` runs in an isolated `HERMES_HOME`.
   Weekly/manual only — cost and latency make per-PR gating wrong.
3. **Fresh-agent docs eval**: a docs-only agent completes a trivial change
   without missing-context questions (run after instruction rewrites).
4. **Installed-user eval**: clean `HERMES_HOME`, install from `dist`/ZIP,
   `hermes plugins doctor`, load `poteto-mode`, one delegated task
   end-to-end (catches skill-view/script resolution, cf. #168).

## Run

```sh
python3 tools/evals/run.py          # live hermes runs, weekly/manual
uv run --frozen pytest -q tools/tests/test_evals.py   # scoring, no hermes needed
```

## Add a golden task

Drop `golden/<id>.json` with `prompt`, `expect.must_mention`,
`expect.must_not_mention` (Cursor vocab belongs here), and `gates`
(concepts the response must name, e.g. plan/verify/evidence).
