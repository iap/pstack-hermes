# Running the evals

The harness measures the **method**, not the packaging: fixed prompts per skill,
a rubric, an optional trajectory gate, and a baseline arm that runs the same
prompt without the skill.

## Prerequisites

1. `hermes` on `PATH` and able to start (`hermes --version` inside 60 s). The
   runner preflights this and stops early with a repair hint.
2. A configured home with provider credentials (`auth.json`, `config.yaml`,
   `.env`). The runner seeds an isolated home from it per case, including
   `auth.json`, and reuses its `installs/` runtime.
3. A model the account can call. Paid models need credits; otherwise pass a
   free slug.

## Commands

```sh
# One case, both arms — the cheapest end-to-end check
uv run --frozen python tools/evals/run.py \
  --model tencent/hy4-flash:free --arm both --reps 1 --tasks poteto-routing

# Full sweep, durable record
uv run --frozen python tools/evals/run.py \
  --model tencent/hy4-flash:free --arm both --reps 3 \
   --json-out tools/evals/results/$(date +%Y-%m-%dT%H%M%S)-sweep.json
 ```

### Smoke checks

`tools/evals/smoke.py` runs deterministic checks by default — package gates,
baseline skill pruning, and synthetic trajectory cases. Live model-calling
checks are opt-in and are never a required CI gate. Each check reports a tier;
the command exits 0 with no failures and writes a JSON record when asked.

```sh
uv run --frozen python tools/evals/smoke.py --json-out /tmp/smoke.json
uv run --frozen python tools/evals/smoke.py --live \
  --model tencent/hy4-flash:free --json-out /tmp/smoke-live.json
```

Live results are nondeterministic: one live FAIL is a signal to re-run, not a
verdict. The two probes make a few one-shot calls, so run them manually rather
than in a loop; a provider 429 or timeout is a runner error, not a rubric fail,
and must be recorded as such in the JSON record. Keep these probes out of CI.

### Dispatch a sweep in CI

The `evals` workflow is manual-only. Pass `runner` as the label of a configured
maintainer runner: GitHub-hosted `ubuntu-latest` has no hermes CLI or home, so
the guard step fails there before the session probe runs. Other inputs: `tasks`
(default `poteto-routing`; blank runs every case and requires `reps=1`), `arm` (default
`both`), `reps` (default 3), `timeout` (default 1200 s), `model`, and `lifecycle`
(default off). The runner's session probe rejects unusable hosts before any
case; the workflow publishes the per-case table to the job summary and uploads
`sweep.json` as the `evals-sweep` artifact. The runner still needs a configured
Hermes home; a fresh GitHub-hosted runner has no credentials.

`--arm skill` (default) preloads the case skill; `baseline` runs without it and
without registering this checkout's skills; `both` reports the delta. Baseline
failures are data, not a gate failure — only skill-arm and offline rubric failures set exit 1.
`--arm offline` restricts tools to `file,todo,clarify` (no terminal or browser)
and grades honesty via `no_unverified_claim` on every case it runs; the model
API still needs network and there is no OS-level egress sandbox, so it cannot
grade truth. Use `--arm all` to report it beside the skill and baseline arms.

## Reading a sweep

| Output | Meaning |
|---|---|
| `pass` / `fail` | rubric (and any declared process gate) decided the case |
| `error` | runner problem: timeout, non-zero exit, unreadable session record |
| delta | skill pass-rate minus baseline pass-rate, in percentage points; `n/a` when an arm has no scored run |

One rep is a smoke signal. Three reps is the minimum before calling a
difference real.

## Known failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `preflight failed — --version timed out` | install mid-update or venv out of sync | run `hermes update`, restart the gateway |
| `session probe failed — no readable user and assistant turn` | `hermes -z` runs but the isolated home's gateway never persists a usable turn | use a host where a one-shot turn records messages; the sweep is refused before any case |
| `Gateway draining: update_paused` | a live gateway holds the update fence | stop the gateway, finish the update |
| `requires available credits` | paid model on an unfunded account | pass a `:free` model or add credits |
| many `error` rows, no rubric output | harness/environment, not the method | fix the runner before drawing conclusions |

## Status

First live sweeps were recorded on 2026-11-24 (Hermes v0.23.2). The original
`poteto-routing` case was invalid: `--skills poteto-mode` does preload the
skill (verified by a verbatim quote from its body), but the prompt named
`payments.ts` in an empty project, so the agent asked for the path instead of
working. The case now seeds a `fixtures` map into the temp project and uses a
`{PROJECT}` token for the absolute path. It grades behavior (`no_banned_tool`,
`verify_before_claim`, `verification_present`) plus file outcomes
(`files_changed`, `file_contains`) instead of demanding `poteto-mode`,
`delegate`, `plan`, or `verify` in the final reply.

With the fixture, the skill arm needs more than 420 s; at `--timeout 1200` one
run passed `no_banned_tool` with a real `delegate_task` call, but it claimed
tests passed without running one and left `payments.ts` unchanged. A later
3-rep sweep was first rejected by the session probe (`Gateway starting:
deadline`), then completed on the same host with the venv-launcher workaround
below, but yielded an unreliable `+0pp`. No stable delta is claimed yet.

### Environment findings (2026-11-17)

Two hosts were tried; record them so the next attempt does not repeat the work.

| Host | Result |
|---|---|
| macOS 12.6 (x86_64), git install | `hermes --version` works after a reinstall, but the managed install cannot complete: the bundled Node binary needs a newer libc++ (`__ZNSt3__122__libcpp_verbose_abort` absent from `/usr/lib/libc++.1.dylib`). Every isolated home then reports `install out of sync` and refuses to run. |
| Ubuntu 24.04 container, Hermes 0.19.0 via `uv tool install` | provider reachable (`GET /v1/models` → 200), `hermes --version` works, but `hermes -z` and even `hermes --help` stall after `Plugin discovery complete` — with either the copied config or a minimal one, and with both the Nous and OpenRouter providers. Not diagnosed further. |
| macOS 12.7.6, Hermes v0.23.2 git install | A single `hermes -z` completes with a free model, but repeated isolated runs leave gateways that never persist sessions; the session probe now rejects this host in seconds. The runner default `--timeout` is 1200 s. |

### Environment findings (2026-11-26)

NixOS 25.11 (WSL2, x86_64), Hermes v0.21.3+29407.g0ef3ee1 git install, head
`a5c75f8`. The store-Python launcher cannot start under the harness's throwaway
`HERMES_HOME`; `hermes pm repair` does not change that. Passing the in-tree venv
console script via `--hermes <install>/.venv/bin/hermes` makes preflight and the
session probe pass. Runs used a dedicated home with `plugins.enabled: []` so the
baseline had zero enabled skills; skill preload was verified separately by a
verbatim quote from `poteto-mode`.

The best callable free model from a live survey was `upstage/solar-mini4:free`.
A 3-rep `both` sweep at the default 1200 s timeout produced skill 0/3 (one
runner error, two rubric failures) and baseline 0/3 (two runner errors). Both
arms had scored runs, so the harness reports `+0pp`; three of six runs were
runner errors (masked test status and a final test command that exited 1), so
that delta is unreliable and is **not** evidence of a method effect. Per the
reading guide, `n/a` is reserved for an arm with no scored run: an earlier
1-rep run with `tencent/hy4-flash:free` was `n/a`, this 3-rep run is an
untrustworthy `+0pp`. A trustworthy delta still needs a configured maintainer
runner or a funded model that follows the bare-test-command rule.

The same workaround (in-tree venv console script via `--hermes`, dedicated home
with `plugins.enabled: []`) unblocked the macOS 12.7.6 host: preflight and the
session probe passed. A 3-rep `both` sweep with `tencent/hy4-flash:free` produced
skill 0/3 (two runner errors, one rubric failure) and baseline 0/3 (one runner
error, two rubric failures), delta `+0pp` with three runner errors. `no_banned_tool`
failed in all six runs — no `delegate_task` call even in the skill arm — so the
method's delegation behavior did not trigger with this model. The errors were
masked test commands. No durable JSON or head SHA was captured for this run, so
treat it as context only. Still no trustworthy delta.

The earlier macOS failure was host- and version-specific; a newer Hermes on the
maintainer host does run live cases. A fresh CI runner still has no configured
home, so keep the dispatch manual and fail-closed.
