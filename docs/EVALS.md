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
  --model meituan/longcat-2.5:free --arm both --reps 1 --tasks poteto-routing

# Full sweep, durable record
uv run --frozen python tools/evals/run.py \
  --model meituan/longcat-2.5:free --arm both --reps 3 \
  --json-out tools/evals/results/$(date +%Y-%m-%dT%H%M%S)-sweep.json
```

`--arm skill` (default) preloads the case skill; `baseline` runs without it and
without registering this checkout's skills; `both` reports the delta. Baseline
failures are data, not a gate failure — only skill-arm rubric failures set exit 1.

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
| `Gateway draining: update_paused` | a live gateway holds the update fence | stop the gateway, finish the update |
| `requires available credits` | paid model on an unfunded account | pass a `:free` model or add credits |
| many `error` rows, no rubric output | harness/environment, not the method | fix the runner before drawing conclusions |

## Status

No live sweep has been recorded yet. The runner, baseline arm, trajectory
graders, preflight, and JSON record format are in place; the first sweep needs
a host where `hermes` starts and a model the account can call.
