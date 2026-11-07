---
name: setup-pstack
description: Configure which models pstack uses per role and at what reasoning budget, for the default profile or a new poteto profile. Detects your available models and writes a per-role panel beside `config.yaml` in the chosen profile's hermes home, outside the plugin tree, so it survives plugin updates. Use for /setup-pstack, "configure pstack models", "pstack budget", or changing pstack's model choices.
---

# Setup pstack

Write `pstack-models.json` in the chosen profile's hermes home (next to that profile's `config.yaml`: `~/.hermes/` for the default profile on Linux, `%LOCALAPPDATA%\hermes\` on Windows; `$HERMES_HOME/profiles/<name>/` for a named profile) - **outside** the plugin directory. pstack replaces the installed package on every `plugins update`, so a panel written inside the plugin tree is silently discarded, while a file beside `config.yaml` survives reinstalls. Profiles are per-device: this skill configures the local hermes install only.

## Steps

### 0. Choose the profile

Ask first, via `clarify` in the TUI (plain text question outside it). Offer these two options, in this order:

- `default — configure the current profile (recommended)`
- `poteto — create a new profile named poteto and configure it`

`default` is recommended: the panel applies to the running session immediately, with no new profile, gateway, or alias side effects. `poteto` is an isolated poteto-mode workspace (its own `SOUL.md`, skills, and budget), separate from default.

- **default:** the target home is the active profile's home. Continue with the steps below unchanged.
- **poteto, profile does not exist:** ask which existing profile to clone from, via `clarify` over `hermes profile list` (the list marker shows the persistently active profile, not necessarily this session's profile, so do not infer the source from it; suggest the profile this TUI session was launched with, or `default`). Then run `hermes profile create poteto --clone-from <chosen-source>` (copies `config.yaml`, `.env`, `SOUL.md`, and skills; messaging bot tokens are left behind), then `hermes profile show poteto` and use its `Path` as the target home. The current session stays on the active profile, so say plainly that the panel applies once the user restarts under the new profile (`hermes -p poteto chat`, or `hermes profile use poteto`). Check the created profile's skill count (`hermes profile show poteto`); if it is 0, tell the user to run `poteto setup` and install skills before expecting poteto-mode playbooks.
- **poteto, profile already exists:** never delete or recreate it silently, and do not reuse it unasked. Ask via `clarify`: `use existing poteto profile (recommended)` or `stop — I will delete it for a fresh one`. On use-existing, target home is its `Path` from `hermes profile show poteto`. If the user wants a fresh poteto profile, stop, tell them to delete it themselves (`hermes profile delete poteto`) and re-run this skill.
- **Target profile readiness (either poteto case):** before writing any panel, verify the target profile can actually load pstack, by either route: `hermes profile show poteto` (Skills count) with pstack present and enabled in `hermes -p poteto plugins list`, **or** the profile's `skills.external_dirs` config pointing at a pstack skill tree. If neither route makes the pstack skills discoverable there, stop and tell the user to install/enable pstack in that profile first — do not write an orphan panel that no playbook will read.

Every later step in this skill (load current state, write the config, confirm) operates on the target profile chosen here, not necessarily the active session's profile.

### 1. Detect available models

Enumerate the model slugs available in the **target profile** (step 0), not just this session: when the target differs from the active session, detect under it (`hermes -p poteto ...` reads that profile's providers/credentials; its catalog is the dependable source). Catalog presence alone is not confirmed access: accept a real slug only when access under the target profile's credentials is established; otherwise ask the user via `clarify` to confirm access in that profile or choose `inherit-parent`. If you cannot detect any for the target, ask the user to paste the slugs they have access to in that profile. Never write a real slug you have not confirmed is available in the target profile — a slug valid in the active session may be unavailable after `hermes -p poteto chat` loads the target's configuration. `inherit-parent` is always valid even though it is not a detected slug (hermes has no Cursor-style `auto` selector; the parent chat model IS the inherit-parent semantic).

### 2. Load current state

The default role-to-model mapping is the shape shown in step 5 below. If `pstack-models.json` already exists in the target profile's home (step 0), read it and treat its `budget` entry and its role values as the current choices. Otherwise start from these defaults. Do NOT try to recover an older in-package `config/models.json`: a plugin update replaces that file with the shipped default before this skill runs, so anything found there is the default rather than the user's saved choices, and copying it forward would silently discard their configuration. If they expected a configuration to still be there, tell them plainly that an update overwrote it and ask them to re-run setup-pstack. A line whose role is not in step 5 is from a retired role. Drop it.

### 3. Budget, map, and confirm

**(a) Ask for a budget.** Prefer clarify over free text. Offer these four options with these exact labels, and name the current budget when the rule records one.

- `unlimited — keep max`
- `large — xhigh reasoning`
- `medium — high reasoning`
- `small — medium reasoning`

**(b) Apply it.** Build the working table from the skill defaults, and on a re-run keep any role you changed by family, list, or alias (`inherit-parent`). On a fresh configuration every role starts as `inherit-parent` (the parent chat model), so setting concrete slugs is what lets the budget's effort tiers apply. `unlimited` leaves every effort as in that table. `large`, `medium`, and `small` set the effort token of every real slug, panel entries included, to `xhigh`, `high`, or `medium`. The effort token is the last token, or the one before a trailing `fast`, on the ladder `max` > `xhigh` > `high` > `medium` > `low`. If the result is not a detected slug, use the same family's detected slug with the highest effort at or below the target, else mark the role as needing a choice. `inherit-parent` does not change. So `small` turns `claude-opus-5-5-max` into `claude-opus-5-5-medium`, and `grok-4.7-xhigh-fast` into `grok-4.7-medium-fast`.

**(c) Show the roles and confirm.** Show every role with its model, marking any real slug not in the detected set as needing a choice. Also list each line step 2 dropped. Ask whether to accept as-is or change specific roles, offering the detected models plus `inherit-parent` (this role runs on the parent chat model) as the options. Prefer clarify over free text. For panel roles (arena runners, architect runners, interrogate reviewers) the value is a list, and one subagent runs per entry, alias entries included, so the list length sets the count. `arena cross-judge pool` is also a list, but Arena selects one value from it whose model family differs from the parent's when possible. `swarm workers` is the default model for every worker unless a race or comparison assigns another model per arm.

### 4. Validate

Every real slug written must be in the detected set; `inherit-parent` always passes. If a chosen real slug is not available, stop and ask again.

### 5. Write the config

Write `pstack-models.json` in the target profile's home (step 0, next to that profile's `config.yaml`), never inside the plugin directory - a panel stored with the package is lost on the next `plugins update`. One entry per role, using the same labels poteto-mode uses. Overwrite the whole file so re-runs stay idempotent. Shape:

```json
{
  "budget": "unlimited",
  "roles": {
    "feature, refactoring": "inherit-parent",
    "bug-fix": "inherit-parent",
    "perf-issue": "inherit-parent",
    "hillclimb": "inherit-parent",
    "judgment and prose": "inherit-parent",
    "hardest tasks": "inherit-parent",
    "how explorer": "inherit-parent",
    "how explainer": "inherit-parent",
    "how critics": ["inherit-parent"],
    "why investigators": "inherit-parent",
    "why synthesizer": "inherit-parent",
    "reflect tooling": "inherit-parent",
    "reflect judgment, divergent, synthesizer": "inherit-parent",
    "arena runners": ["inherit-parent"],
    "arena cross-judge pool": ["inherit-parent"],
    "swarm workers": "inherit-parent",
    "architect runners": ["inherit-parent"],
    "interrogate reviewers": ["inherit-parent"]
  }
}
```
Panel roles (how critics, arena runners, arena cross-judge pool, architect runners, interrogate reviewers) take an ARRAY; one subagent runs per entry, so the list length sets the count. `swarm workers` is the default for every worker unless a race assigns another model per arm.

### 6. Confirm

Tell the user the rule was written for the target profile (name it) and that it applies to new sessions under that profile. If the target is a `poteto` profile the current session is not running under, add the restart command (`hermes -p poteto chat`). Re-running this skill updates it.

### 7. Offer a verification skill (optional)

Check whether the project has a way to drive the real app for proof (a `verify-*` skill, or an existing harness). If not, offer once: "want a project-local verification skill, so agents can drive the app the way a user does and prove changes work? I can generate one with /create-verification-skill." On yes, load the create-verification-skill skill via skill_view (it ships in this plugin) and follow it. On no, move on without pushing.
