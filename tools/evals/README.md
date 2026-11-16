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
4. **Installed-user lifecycle** (`install_smoke.py`): clean `HERMES_HOME`,
   install the published package, `hermes plugins doctor --ci`, assert the
   shipped tree (every skill, root `scripts/`, dual lockfile, model panel),
   then `plugins remove` and assert the directory and listing entry are gone,
   reinstall pinned to the installed commit, and `plugins update` — re-asserting
   the tree after each stop. Catches the class behind #168 and #169, which no
   static gate can see. Needs the `hermes` CLI; no provider credentials.

## Run

```sh
python3 tools/evals/run.py          # live hermes runs, weekly/manual
python3 tools/evals/install_smoke.py                # full lifecycle: install, remove, reinstall, update
python3 tools/evals/install_smoke.py --no-lifecycle # install + doctor only
python3 tools/evals/install_smoke.py --keep         # keep the temp HERMES_HOME
uv run --frozen pytest -q tools/tests/test_evals.py tools/tests/test_install_smoke.py
```

## Add a golden task

Drop `golden/<id>.json` with `prompt`, `expect.must_mention`,
`expect.must_not_mention` (Cursor vocab belongs here), and `gates`
(concepts the response must name, e.g. plan/verify/evidence).

## Known limitation: oneshot cwd

`hermes -z` does not seed a working directory (the fix is archived in
`patches/archive/README.md`, not applied). Prompts that create or edit files
must pass **absolute paths**; relative paths may resolve against the wrong
directory. The runner sets the process cwd, which is not the same thing.

## Optional process gates

A golden case can also grade what the agent **did**, using the isolated run's
session record (`$HERMES_HOME/state.db`):

```json
{
  "id": "fix-and-verify",
  "skill": "poteto-mode",
  "prompt": "Fix the failing test in calc.py, then run it.",
  "expect": {"must_mention": ["calc.py"]},
  "process": {"gates": ["read_before_write", "verify_before_claim"]}
}
```

- `read_before_write` — the first interaction with a `patch`ed path must be a
  `read_file` of the same resolved path. Read-then-patch passes; patch-then-read
  fails. A path never read with `read_file` is **not** a failure (it may have
  been read with `cat`), and `write_file` is ungraded (creating a file needs no
  prior read). `execute_code` that writes, or a V4A `patch` without a path,
  makes the gate `unavailable`.
- `verify_before_claim` — a tests-pass claim in the final response requires a
  real test command with exit 0 earlier in the session. `cat pytest.ini` and
  `pytest --collect-only` do not count. No claim → `not_applicable`.

`unavailable` is reported as a runner error, never folded into a pass: a grader
that cannot see the evidence says so. Both gates are unit-tested against
synthetic session databases (`tools/tests/test_trajectory.py`).
