# pstack

*The pstack agent method — go fast by going deep first — packaged for the
Hermes Agent portable plugin path. Adapted from
<https://github.com/cursor/plugins/tree/main/pstack> (MIT, © Lauren Tan);
the package is maintained here and its version is locally owned.*

## Install

Install the plugin:

```sh
hermes plugins install iap/pstack-hermes --enable
```

Unpinned installs update with `hermes plugins update pstack`.

Pinned installs must be reinstalled with a new SHA and `--force`.

GitHub Releases record package SHAs for immutable root installs. Pinned
installs do not auto-update; to move an existing pin, use `hermes plugins
install iap/pstack-hermes --ref <new-package-SHA> --force --enable`.

## First run

1. `hermes plugins doctor pstack --ci` — manifest parses, all skills discover.
   Pick the target explicitly: `pstack` is ambiguous (repo root = local
   directory; elsewhere = installed package). Use the name as installed for
   the dist package, or a resolved local path for a branch tree.
2. Load the `setup-pstack` skill once - it writes `pstack-models.json` beside hermes' `config.yaml`, outside this package, so plugin updates do not discard it
   (the 18-role model panel the workflow skills read).
3. Load `poteto-mode` and give it a real task — it classifies the work and
   routes to the right playbook. You do not pick playbooks yourself.

Skills are opt-in on the portable path: load one with
`skill_view` id `agent-plugin-pstack-<digest>:<skill-name>` (digest = first
8 hex of the sha256 of the plugin key, stable while the install dir is named
`pstack`). For `/<name>` slash commands instead, add this package's `skills`
dir to `skills.external_dirs` in the hermes `config.yaml` — trade-off: skills
enter the prompt index with 60-char descriptions and lose the namespace.

## Update

> [!WARNING]
> Existing installs with a locally generated untracked `package-lock.json`:
> back it up and remove it from the installed plugin directory before
> updating (confirm untracked status with `git -C <plugin-dir> ls-files
> --error-unmatch package-lock.json`), so the updater does not stash-restore
> it over the now-tracked file and strand other local edits.

```sh
hermes plugins update pstack
```

Unpinned root installs update in place. Pinned installs must be reinstalled
with a new SHA and `--force` (see [Install](#install)).

Installs created before the root-layout migration (the old
source-subdirectory route) cannot update in place. Back up local edits,
remove the old install, then install the root package:

```sh
hermes plugins remove pstack
hermes plugins install iap/pstack-hermes --enable
```

If the old install was pinned, add `--ref <new-package-SHA>` to the install
command.

## Customizing skills

- **Tweak a line or two** — edit the installed `SKILL.md`, restart the
  gateway, and save a backup outside the plugin before updating. Git-backed
  updates autostash and re-apply local edits (conflicts stay in `git stash`);
  reinstalls replace shipped skills, so in-place edits are temporary.
- **Own several changed skills** — fork `iap/pstack-hermes`, commit, install from
  your fork (`hermes plugins install <you>/pstack-hermes --enable`).
- **Add your own new skills alongside** — a skill tap:
  `hermes skills tap add <you>/skills-repo`, then
  `hermes skills install <you>/skills-repo/<skill>`.
- Keep the hermes vocabulary when editing (`delegate_task`, `clarify`,
  `session_search`, `hermes cron`); Cursor primitives will mislead the agent.

Problems: port behaviour → <https://github.com/iap/pstack-hermes/issues>;
a hermes defect that reproduces with the plugin disabled →
`NousResearch/hermes-agent`; an upstream pstack bug → `cursor/plugins`.

## What hermes loads

- **49 skills** (26 workflow/mode +
  23 `principle-*`), single-level `skills/<dir>/SKILL.md`,
  discovered via the root `plugin.json` (agent-plugins-v1 manifest,
  9 whitelisted fields).
- `skills/hermesbot/` — hermes-native control-surface skill on the gateway
  webhook (`X-Webhook-Signature-V2` HMAC) plus `hermes send` / `hermes peer`;
  fills the excluded `make-bot-ui` slot.
- Skill scripts (e.g. `scripts/`) ship verbatim; the loader
  never executes them, but skills instruct the agent to run them (`bun`, `gh`).

- `skills/hermes-vocabulary/` — disambiguation table (hermes ↔ Cursor terms),
  single home for `delegate_task`, `clarify`, `hermes cron`, `goal.md`, etc.
- `skills/hermes-troubleshooting/` — routes Hermes-host trouble to the
  `hermes-guide` diagnosing skills when `iap/hermes-guide` is installed
  (`diagnosing-triage` → `diagnosing-*`); otherwise points at
  `hermes plugins doctor` and the Hermes guide.

Not shipped: `automations/benny/` and `skills/make-bot-ui/` (install-scanner
verdicts — persistence / privilege escalation; `--force` cannot override) and
upstream's `docs/guide/` (read it upstream for the guided tour). This tree is
Hermes-native only; for real Cursor-side work install upstream pstack.

## Differences from upstream

| Pass | What changed |
|---|---|
| manifest | root `plugin.json` injected: exact agent-plugins-v1 `$schema`, 9-field whitelist |
| frontmatter | `poteto-mode` name fixed to kebab-case (loader requirement) |
| R1 | poteto-mode principles index kept in sync with the 23 leaves (validate.py R1) |
| F16 | retired at c47b1284: upstream ships a slug-agnostic lane regex |
| F10–F12 | `worktree-audit.sh` portable (GNU/BSD), space-safe |
| F-publish | `benny` + `make-bot-ui` excluded (scanner verdicts); `hermesbot` fills the slot; 3 localhost literals neutralized |
| T8/T9/T10 | `setup-pstack` writes the model panel beside hermes' `config.yaml` (outside the package, so updates do not discard it); discovery via `session_search`; hermes tool names |
| Phase-2A | delegation vocabulary → `delegate_task` / `clarify` package-wide |
| T11 | hardcoded Cursor paths → hermes equivalents |
| T12 | `/loop` → `hermes cron` wake; `/goal` → `goal.md` in the agent store |
| T13 | residual vendor coupling reworded (`cursor-team-kit`, cloud fleet, `gt`) |
| T14 | stacker-role / topology re-pointed (issue #33) |
| T15 | `orch frontier set` provider selection: `auto` / `graphite` / `github` |
| G1 | delegation escape hatch: in-thread surgical edits with mandatory delegate review |

Text is otherwise unchanged; the pass ledger with reviewer checks lives in
[issue #94](https://github.com/iap/pstack-hermes/issues/94), and
CHANGELOG.md records the shipped changes.

## Known limitations (documented, not drift)

- Node tooling ships dual lockfiles (`bun.lock` + `package-lock.json`) so
  hermes' `npm ci` sidecar works on install and update (#169). Bun bumps
  must regenerate both locks; CI fails a desynced pair. Existing installs
  with a locally generated untracked `package-lock.json`: back it up, then
  remove it from the installed plugin directory before updating (confirm it
  is untracked there first with `git -C <plugin-dir> ls-files
  --error-unmatch package-lock.json`, which fails when the file is not
  tracked; `git status --porcelain` alone cannot distinguish ignored from
  tracked-clean), so the updater does not stash-restore it over the
  now-tracked file and strand other local edits.
- `deslop`, `control-ui`, `control-cli` are named by playbooks but ship
  outside this package; a verdict without its demanded live lane is
  incomplete, not clean. (`no-comments`, `unslop`, `technical-writing` ship.)
- `orch frontier set` providers: `auto` (Graphite first, then GitHub-native
  PR base/head topology), `graphite`, `github`. GitLab reserved, not
  implemented.
- Stack topology needs Graphite (`gt`): restacks, stack surgery, and the
  stack-aware merge queue have no hermes equivalent. GitHub-native stacked
  PRs (`gh stack`) cover some stack operations; ordinary base changes go
  through the forge and need no stacker.
- No `mcp.json` shipped: research skills use whichever MCP servers the
  session configures; unreachable sources are recorded as null findings,
  never invented.

---

Adapted for Hermes Agent plugin compatibility from github.com/cursor/plugins pstack.
