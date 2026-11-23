# Model mapping (for now)

pstack picks a model per role. Three layers, highest precedence first:

1. **Your panel** — `pstack-models.json` beside the hermes `config.yaml`
   of the profile you configure (written by `setup-pstack`; survives
   plugin updates). `/setup-pstack` first asks which profile: `default`
   (the current profile, recommended — applies to the running session
   now)    or `poteto` (creates a new `poteto` profile via
   `hermes profile create poteto --clone-from <chosen-source>`, writes
   the panel under the `Path` reported by `hermes profile show poteto`,
   and applies after restarting with `hermes -p poteto chat`; an
   existing `poteto` profile is only reused after the user confirms
   it). Each profile keeps its own panel, and
   profiles are per-device: setup configures the local hermes install
   only.
2. **The shipped panel** — `config/models.json` inside the package. A documented
   reference of the defaults, re-verified against the provider catalog by
   `model-drift-watch`; skills do not read it at runtime. A role uses your panel
   when it exists, otherwise the effective delegation model (`delegation.model` from `config.yaml` when set, otherwise the parent chat model) (layer 3).
3. **The method text** — skills name a panel role line, not a concrete
   model. With no panel or role line they omit `model` and run on the
   effective delegation model (`delegation.model` from `config.yaml` when set,
   otherwise the parent chat model). The upstream Cursor-family names (`grok-4.7-xhigh-fast`,
   `claude-opus-5-5-max`, `gpt-5.6-sol-max`) survive only as effort-tier
   examples in `setup-pstack`; the mapping below is the shipped panel's provenance.

## Upstream name → hermes-side default

| Upstream name in the method text | Roles it defaults | Hermes-side default, for now |
|---|---|---|
| `grok-4.7-xhigh-fast` | `feature, refactoring`, `bug-fix`, `perf-issue`, `hillclimb` | `z-ai/glm-5.2` |
| `grok-4.7-xhigh-fast` | `swarm workers`, `how explorer` | `inherit-parent` |
| `claude-opus-5-5-max` | `judgment and prose`, `how explainer` | `inherit-parent` |
| `claude-opus-5-5-max` | `why synthesizer`, `reflect judgment, divergent, synthesizer` | `z-ai/glm-5.2` |
| `gpt-5.6-sol-max` | `interrogate` reviewer slots | the `interrogate reviewers` list below |
| `inherit-parent` | any role set to it | omit `model`; the effective delegation model (`delegation.model` from `config.yaml` when set, otherwise the parent chat model) |

The `vendor/model` values are ids from the provider catalog the tooling checks
against (OpenRouter); the weekly `model-drift-watch` workflow re-verifies every
configured slug and opens a tracking issue when one leaves the catalog. **This
mapping is provisional ("for now")** — it moves when upstream renames models or
the panel is refreshed, and `setup-pstack` lets you override every row.

## The shipped panel

`config/models.json` (shipped defaults at package root; 18 roles):

| Role | Default |
|---|---|
| feature, refactoring | `z-ai/glm-5.2` |
| bug-fix | `z-ai/glm-5.2` |
| perf-issue | `z-ai/glm-5.2` |
| hillclimb | `z-ai/glm-5.2` |
| judgment and prose | `inherit-parent` |
| hardest tasks | `z-ai/glm-5.2` |
| how explorer | `inherit-parent` |
| how explainer | `inherit-parent` |
| how critics | `inherit-parent`, `meta/muse-spark-1.2-contributor` |
| why investigators | `inherit-parent` |
| why synthesizer | `z-ai/glm-5.2` |
| reflect tooling | `qwen/qwen3-30b-a3b-instruct-2507` |
| reflect judgment, divergent, synthesizer | `z-ai/glm-5.2` |
| arena runners | `inherit-parent`, `meta/muse-spark-1.2-contributor` |
| arena cross-judge pool | `z-ai/glm-5.2`, `inherit-parent` |
| swarm workers | `inherit-parent` |
| architect runners | `z-ai/glm-5.2`, `meta/muse-spark-1.2-contributor` |
| interrogate reviewers | `z-ai/glm-5.2`, `inherit-parent`, `meta/muse-spark-1.2-contributor` |

## Example `pstack-models.json`

`setup-pstack` writes one entry per role and overwrites the whole file on
re-runs, so it stays idempotent. A minimal user panel looks like:

```json
{
  "budget": "unlimited",
  "roles": {
    "feature, refactoring": "z-ai/glm-5.2",
    "bug-fix": "z-ai/glm-5.2",
    "judgment and prose": "inherit-parent",
    "swarm workers": "inherit-parent",
    "arena cross-judge pool": ["z-ai/glm-5.2", "inherit-parent"]
  }
}
```

Run the `setup-pstack` skill to generate the full file (it detects the models
you actually have and applies the effort tiers); edit it directly for one-off
changes.

## Related

- `tools/slug_drift.py` — validates every configured slug against the live
  catalog; `--prose` also scans skill text for stale slug mentions.
- Panel storage: kept outside the package so `hermes plugins update` never
  discards it.
