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
4. **Installed-user eval** (`install_smoke.py`): clean `HERMES_HOME`, install
   the published package, `hermes plugins doctor --ci`, assert the shipped tree
   (every skill, root `scripts/`, dual lockfile, model panel), then
   `hermes plugins update` and re-assert. Catches the class behind #168 and
   #169, which no static gate can see. Needs the `hermes` CLI; no provider
   credentials.

## Run

```sh
python3 tools/evals/run.py          # live hermes runs, weekly/manual
python3 tools/evals/install_smoke.py                # installed-user smoke, no credentials
python3 tools/evals/install_smoke.py --keep         # keep the temp HERMES_HOME
uv run --frozen pytest -q tools/tests/test_evals.py tools/tests/test_install_smoke.py
```

## Add a golden task

Drop `golden/<id>.json` with `prompt`, `expect.must_mention`,
`expect.must_not_mention` (Cursor vocab belongs here), and `gates`
(concepts the response must name, e.g. plan/verify/evidence).
