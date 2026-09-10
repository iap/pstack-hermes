# Study-vs-shipped review — pstack-hermes-adaptation-study re-read against reality

> **Purpose:** re-read the adaptation study (the 4 chapters + the findings index +
> the R1–R3 harness reviews) against what the port actually *became* — flag every
> claim that was implemented, superseded, is stale, or is still open; identify the
> issues, bugs, and redundancies; and extract the optimal next moves for
> Hermes-agent itself.
> **Method:** poteto-mode interrogation — three adversarial lenses (study-fidelity,
> shipped-reality, harness-gap) + lead synthesis.
> **Baseline:** study @ pstack v0.14.4 / pin `799151d`; shipped @ main `5b09fe3`,
> pstack 0.14.8, 45 skills.

---

## Reviewer 1 — study fidelity: what the study promised vs what shipped

| Study claim (chapter / finding) | Shipped reality | Verdict |
|---|---|---|
| 45-skill portable package (ch. 1) | 44 + hermesbot = **45 skills**, validated, installed | ✅ shipped + expanded |
| T1–T11 transforms (ch. 3) | `tools/convert.py`, all anchors enforced fail-loud; T11 shell-script pair **silently never applied** → caught by the anchor audit (PR #5) | ✅ shipped + hardened |
| Config models.json panel (ch. 2, F-panel) | shipped as inherit-parent defaults → **Stage-D panel applied** (PR #4): 18 roles mapped | ✅ shipped + expanded |
| Worktree playbooks work on hermes (ch. 2) | playbooks ship; worktree isolation *per subagent* is NOT a hermes primitive (the skills manage worktrees themselves) | ⚠️ partially — see gap W1 |
| Hooks parity (ch. 2) | hermes hooks supported; the continual-learning-style hooks pattern works | ✅ no gap |
| Dashboard/UI canvases (ch. 2, PR-review-canvas/docs-canvas equivalents) | hermes has **no canvas surface**; the plugin ships a local-HTML dashboard pattern (serve → webchat) | ⚠️ gap C1 — workaround exists |
| Benny automations (ch. 1, excluded by the scanner) | excluded, then **superseded by hermesbot** (webhook subscriptions + signed notifications + peer gateways, written natively) | ✅ Phase-4 closed by substitution |
| The marketplace breadth (ch. 1, 50+ third-party MCPs) | not a harness gap — Hermes speaks MCP; the ecosystem is a community-time matter | ➖ not actionable |
| Installation: scanner-clean, loader-verified (ch. 4) | clean-room verified on Windows + Linux; the subdir install flow documented | ✅ proven |
| Upstream pinning + drift (ch. 4) | UPSTREAM_PIN + the drift watch + the anchor audit; **0.14.8 drift landed** (PR #6) with the anchor audit naming reworded models | ✅ shipped + exercised |
| Delegation translation: Task → delegate_task (ch. 3, F-delegation) | complete; verified in the live sessions (293-turn poteto-mode run) | ✅ shipped |

**Study-fidelity verdict:** every load-bearing claim in the study either shipped
or was consciously superseded. Zero study findings turned out to be wrong about
the platform — two were *incomplete* (worktree isolation, canvases), and those
are now the top harness-gap entries below.

---

## Reviewer 2 — shipped-reality: issues, bugs, redundancies in what shipped

**Findings (each verified this pass):**
1. **[Fixed] The silently-unapplied transform** — the T11 shell-script pair never
   ran; the anchor audit (PR #5) converted the failure class from silent to
   build-failing. Redundancy lesson: anchors without hit-counts rot.
2. **[Fixed] The models/binaries verification asymmetry** — GGUFs sha256-verified,
   release binaries not; closed by the tamper-evidence record (hermes-llama
   PR #35) and flagged for pstack's release artifacts.
3. **[Fixed] The panel's env-restore + the deterministic fixture** — the Greptile
   P1/P2 round on the digest tests.
4. **[Redundancy — pruned] The duplicated ban lists** (validate.py inline vs the
   CI scanner gate) — unified into `tools/bans.py` (PR #5).
5. **[Redundancy — pruned] The labeler create-only flow** — replaced by the
   ensure-labels improvement (#11).
6. **[Redundancy — intentional] The dual `.cursor-plugin` surface** — inert on
   hermes, kept deliberately for dual-load; costs one manifest + one agents dir.
7. **[Still open — by design] The fallback-collapse finding** — provider 500s
   collapse the panel's diversity to one model (the Level-2 test). Documented;
   the fix is an upstream feature (W2 below), not a plugin patch.

---

## Reviewer 3 — harness gap: Cursor vs Hermes, and where Hermes is more

| Capability | Cursor | Hermes | Gap / Plus |
|---|---|---|---|
| Model choice per subagent | ✅ per-subagent `--model` | ✅ `delegate_task` model param + the 18-role panel | ✅ closed — and the panel is *declarative*, which Cursor lacks |
| Worktree isolation per subagent | ✅ worktree-based orchestration | ❌ subagents share the agent's cwd; isolation is skill-managed | **W1 — the structural gap** |
| Hooks (session-start, etc.) | ✅ hooks.json | ✅ hooks supported (manifest v2) | ✅ no gap |
| Visual canvases (PR-review-canvas, docs-canvas) | ✅ native canvas UI | ❌ no canvas; local-HTML-serve pattern works | **C1 — gap**; the local-serve pattern is the hermes-native workaround |
| Scheduled automations (benny) | ✅ cloud automation agent | ✅ **gateway cron + webhook subscriptions** — no cloud dependency | ➕ **Hermes-plus**: local-first, self-hosted automation |
| Signed notifications / peer gateways | ❌ not a Cursor pattern | ✅ hermes webhook stack | ➕ **Hermes-plus** |
| Local GGUF models (offline, no subscription) | ❌ cloud models only | ✅ **llama.cpp provider (hermes-llama)** | ➕ **Hermes-plus**: offline/air-gapped/private inference |
| Self-diagnosis of the platform | ❌ no self-doctor | ✅ hermes-guide: the agent diagnoses its own config/skills/hooks | ➕ **Hermes-plus** |
| Provider fallback chains | ✅ model fallback | ✅ provider fallback — **but it collapses panel diversity** | **W2 — the finding from real usage** |
| Declarative role→model panel | ❌ per-invocation only | ✅ config/models.json, 18 roles | ➕ **Hermes-plus** |
| Plugin marketplace breadth | ✅ 50+ third-party MCPs | ➖ smaller ecosystem, same MCP protocol | ➖ time/community, not harness |
| Skill format | SKILL.md | SKILL.md | ✅ identical |

---

## The synthesis — optimal solutions

### Close the gaps (without re-importing Cursor needs)
- **W1 (worktree isolation):** do NOT build hermes-side worktree plumbing; the
  skills already manage their own worktrees (the worktree-cleanup playbook), and
  that keeps the harness simple. Long-term: propose `--worktree` on
  `delegate_task` upstream *only if* the orchestrate playbook's parallel flows
  hit real cross-contamination.
- **C1 (canvases):** keep the local-HTML-serve pattern; do not chase Cursor's
  canvas UI. The pattern is already proven (the pstack dashboard).
- **W2 (fallback collapse):** the one real harness improvement. Design: per-slot
  *diversified fallback chains* — when a slot's provider fails, fall back to a
  model from a DIFFERENT provider family (preserving panel diversity under
  failure). File as an upstream feature request after #102331 lands.

### Leverage the pluses (Hermes-only capabilities)
- **Local GGUF inference** (hermes-llama) for the fan-out roles: offline,
  rate-limit-immune, private — Cursor cannot do this at all.
- **Gateway cron automations** replacing benny-class agents: scheduled,
  self-hosted, webhook-driven.
- **Self-diagnosis loops** (hermes-guide) as a standard for every hermes plugin.

### Guard against re-importing Cursor needs
- The skills must never *require* Cursor surfaces to function (the dual-load
  surface stays inert-and-optional).
- The panel/fallback design must degrade to hermes-native behavior
  (inherit-parent), never to a Cursor-shaped dependency.
- The drift watch keeps the upstream sync a *reviewed choice*, not a
  compatibility chase.

---

## Long-term goals (see docs/LONG-TERM-GOALS.md)

1. **Panel-first operation** — Stage-D proven in weekly use; the fallback
   diversity upstream PR (#W2) submitted and merged.
2. **Local-model tier** — hermes-llama promoted from a plugin to the default
   fan-out tier for the rate-limit-heavy roles (offline/private inference).
3. **Self-diagnosis standard** — every hermes plugin in the portfolio ships a
   doctor-style check + the drift watch (the hermes-guide pattern generalized).
4. **Zero Cursor dependency** — the dual-load surface retires when Cursor-specific
   content is no longer referenced by any active flow; the port becomes
   hermes-first with upstream attribution.
