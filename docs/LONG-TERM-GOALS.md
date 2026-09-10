# Long-term goals — pstack-hermes program

> **Purpose:** the durable goals for the pstack-hermes program, derived from the
> adaptation study re-read against shipped reality (docs/STUDY-VS-SHIPPED-REVIEW.md).
> **Design rule:** close gaps with Hermes-native capability, never by importing
> Cursor needs; treat Hermes-only strengths as the leverage.

## G1 — Panel-first operation
**Goal:** the 18-role model panel is the default operating mode, proven in
weekly real use; the panel's diversity survives provider failures.
- Evidence: Level-2-style sessions with multi-provider delegates; no fallback
  collapse on healthy providers.
- Dependency: W2 (below) for the failure path.
- Trigger to act: a real session where the collapse costs quality.

## G2 — Diversified provider fallback (upstream)
**Goal:** hermes-agent falls back across provider *families* on failure, so
panel diversity survives provider 500s — instead of collapsing to one model.
- Form: an upstream feature request/PR after #102331 lands (evidence: the
  Level-2 test's collapse finding, documented).
- Acceptance: a failed muse-spark slot falls back to a non-longcat model when
  the panel declares diversity.

## G3 — Local-model tier (hermes-llama)
**Goal:** hermes-llama's llama.cpp provider becomes the default tier for the
rate-limit-heavy roles (swarm/arena runners), with the cloud panel as the
quality tier — offline/private/rate-limit-immune operation.
- Milestones: the tamper-evidence PR merged (PR #35 ✓ done); a smoke-tested
  local-model session driving real pstack work; the panel's runner roles
  point at local models as the second entry.

## G4 — Self-diagnosis standard (hermes-guide pattern)
**Goal:** every hermes plugin in the portfolio ships the hermes-guide pattern:
a doctor-style check, drift-checked constants, and the version-pinned accuracy.
- Milestones: the pstack doctor continues ✓; the pattern documented and
  reusable; each new plugin starts from the pattern.

## G5 — Zero Cursor dependency
**Goal:** the port is hermes-first: no active flow references Cursor surfaces;
the dual-load manifest retires when the dual-load use ends.
- Guard: the skills never require Cursor APIs to function; the upstream sync
  stays a reviewed choice (the drift watch), not a compatibility chase.
- Retirement trigger: one full quarter of hermes-only usage with no dual-load
  need.

## G6 — Automation without cloud (gateway-native)
**Goal:** benny-class automations (triage, reproduce, schedule) run on the
gateway's own cron + webhooks — self-hosted, signed, local-first.
- Milestones: hermesbot's webhook flow in weekly use; the automation recipes
  documented as hermes-native patterns (no cloud dependency).

## G7 — The process standard (the operating checklist)
**Goal:** the before-you-act checklist (OPERATING-CHECKLIST.md) governs every
action in this program — external, public, multi-step — and is amended by
incident, reviewed with the owner.
- Function: every failure class caught by a gate, not by memory.
