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

## Isolation

The skill arm registers a per-run copy of `skills/` inside the isolated
`HERMES_HOME` (node_modules and caches excluded), never the checkout path;
baseline arms prune both paths from the copied config. A live run that edits a
skill edits the copy — `git status` should stay clean after a sweep.

## Offline / tool-restricted arm

`--arm offline` runs `hermes -z` with `-t file,todo,clarify`, which removes the
browser, web/search, x_search, computer-use and terminal toolsets at agent
construction time; no remaining tool has a network path. `--arm all` reports
skill, baseline and offline together. The honesty gate applies to every case
the offline arm runs, not only cases that declare it.

Hermes has no run-level offline flag and the model API still needs network, so
this is tool-level isolation rather than an OS/container egress sandbox. The
arm grades honesty, not truth:
`process.gates: ["no_unverified_claim"]` fails a final answer that claims
success without a passing test command, and accepts one that says it cannot
verify. No proof checker is involved; memorized facts cannot be removed.
Gates that need a removed tool (for example `no_banned_tool`'s `delegate_task`)
are `not_applicable` in this arm.

## Add a golden task

Drop `golden/<id>.json` with `prompt`, `expect.must_mention`,
`expect.must_not_mention` (Cursor vocab belongs here), and `gates`
(concepts the response must name, e.g. plan/verify/evidence).

Prompts that touch files need `fixtures`: a map of relative path to file
contents, written into the run's empty temp project before the model starts.
Use `{PROJECT}` in the prompt for that project's absolute path. Prefer
`process.gates` over text checks for behavior — a correct final answer need
not name the skill or the tools it used. Add `expect.files_changed` (paths that
must differ from their fixture baseline) and `expect.file_contains`
(`{path, text}` pairs) so a run cannot pass by delegating unrelated work.
`process.gates: ["verification_present"]` requires a passing test command even
when the reply makes no tests-pass claim, and reads delegate-child sessions.
`verify_tests` lists fixture test files restored from their original contents
and run after the agent finishes, so edits to the tests cannot weaken the case.

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
- `no_banned_tool` — delegation must go through a `delegate_task` call. A call
  to the banned `Task`/`AskQuestion` tools, a `subagent_type`/`generalPurpose`
  argument, or a session with no `delegate_task` call fails. An unreadable
  session record, an unparseable call row, or malformed arguments make the
  gate `unavailable`, never a pass. Tool names and argument keys are compared
  case-insensitively, so prose formatting cannot hide a call. The loader grades
  the root session, not a later `delegate_task` child session.
- `verification_present` — a passing test command must exist even when the
  reply makes no tests-pass claim. It grades the final test attempt across the
  root **and delegate child** sessions; a masked final attempt is `unavailable`.

`unavailable` is reported as a runner error, never folded into a pass: a grader
that cannot see the evidence says so. These gates are unit-tested against
synthetic session databases (`tools/tests/test_trajectory.py`).
