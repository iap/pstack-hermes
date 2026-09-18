# Using pstack on hermes

> [!NOTE]
> This page covers **how to invoke and configure** the package on hermes. It
> does not explain the method — that lives in the skills themselves (load
> `poteto-mode` first; it routes to the rest). For the original method
> documentation, see upstream:
> <https://github.com/cursor/plugins/tree/main/pstack>.

## What you installed

A **method package**: 45 instructions-for-the-agent skills (a router, 23
playbooks, workflow skills, and 21 principles) plus the converter/validator
tooling that keeps them faithful to upstream. It is not a service, a daemon, or
an autopilot — it changes how the agent works on a task you give it.

## Invocation model

Portable-plugin skills are **opt-in**: they do not enter the system-prompt skill
index by default. Two supported routes:

| Route | How | Trade-off |
|---|---|---|
| Namespaced `skill_view` | load a skill by id `agent-plugin-pstack-<digest>:<skill>` | keeps the plugin namespace; nothing appears in listings |
| `skills.external_dirs` | add this package's `skills/` dir to the hermes config | registers `/<name>` slash commands and lists the skills; loses the namespace and adds 60-char descriptions to the prompt index |

Pick one. The namespaced route is the default; `external_dirs` is the
convenience route when you want `/poteto-mode` style commands.

## First run

1. **Install** (see the README for the exact command), then run
   `hermes plugins doctor pstack --ci` — the manifest must parse and all skills
   must be discovered.
2. **Configure the model panel** — run the `setup-pstack` skill once. It writes
   `config/models.json` mapping pstack's roles (code, prose, judgment, tooling,
   cross-judge, and the panel roles) to models available to you. `inherit-parent`
   means "use the parent chat model". The shipped workflow skills consume their
   roles from it — `why`, `reflect`, `arena`, and `interrogate` name the file
   directly; `how` reads `your configured how-explorer model` / `the configured
   how-critics list`; `swarm` reads `swarm workers` from `the configured pstack
   model panel`. A bad slug here is a local config problem that shows up later,
   at delegation time — not an upstream bug.
3. **Give it a real task** and load `poteto-mode`. It classifies the work and
   routes to the right playbook; you do not pick the playbook yourself.

## What to expect

- **The agent follows playbooks, not the docs.** Your leverage is in the task
  statement and in the gates the playbooks impose (verification, decision
  trails) — not in re-reading instructions.
- **External prerequisites stay external.** Some playbooks name tooling this
  package does not ship (a deslop pass, live control-surface drivers) and some
  capabilities are approximated for hermes (see the package README's Known
  limitations and [ADAPTATIONS.md](ADAPTATIONS.md)). When a demanded live lane
  is unavailable, a verdict is *incomplete*, not clean.
- **MCP-dependent skills adapt.** Research skills draw on whichever MCP servers
  your session has configured; unreachable sources are recorded as null
  findings, not invented.

## Customizing skills

Pick by what you want to change — one of three routes:

- **Tweak a line or two (model slug, thresholds, wording) — edit in place.**
  The installed plugin is plain files under the hermes plugins dir; edit any
  `SKILL.md`, then `hermes gateway restart`. Nothing re-scans local edits.
  On a root install (`iap/pstack`), `hermes plugins update pstack`
  autostashes uncommitted edits and reapplies them — keep them uncommitted;
  locally committed changes block the fast-forward update. Subdir installs
  have no `.git`: reinstalling to update **wipes** in-place edits, so copy
  modified skills out first.
- **Own several changed skills, keep them versioned — fork the dist repo.**
  `iap/pstack` is the plain package (manifest at root, no tooling): fork it,
  commit your changes, install from your fork
  (`hermes plugins install <you>/pstack --enable`). Updates become a normal
  git pull/merge from upstream.
- **Add your own new skills alongside pstack — a skill tap.** A tap is just
  a GitHub repo of `skills/<name>/SKILL.md` directories:
  `hermes skills tap add <you>/skills-repo`, then
  `hermes skills install <you>/skills-repo/<skill>`. No fork of pstack, no
  touching the installed tree; pstack's own skills stay stock.

Structural changes that must survive upstream re-pins (new adaptations,
model-panel defaults, exclusions) belong in a fork of the development repo
(`pstack-hermes`), via the converter — see its CONTRIBUTING.md. Broadly
useful fixes are welcome as PRs there.

> [!WARNING]
> Keep the hermes vocabulary when editing skills — `delegate_task`,
> `clarify`, `session_search`, `hermes cron`, `hermesbot`. Nothing on your
> machine enforces this; a skill that instructs Cursor-style `Task`
> subagents or `AskQuestion` will silently mislead the agent on hermes.

## Reporting problems

Read [SECURITY.md](../SECURITY.md) first — it defines what belongs to this port
versus upstream. In short: port behaviour (adaptations, exclusions, config,
install) → this repository's issues; a hermes defect that reproduces with the
plugin disabled → `NousResearch/hermes-agent`; an original Cursor-plugin bug
that reproduces without this port → `cursor/plugins`.

## See also

- [ADAPTATIONS.md](ADAPTATIONS.md) — what changed from upstream and why
- [RUNBOOK-upstream-drift.md](RUNBOOK-upstream-drift.md) — re-pinning procedure
- [PATCHES.md](PATCHES.md) — hermes-fork patches (historical)
