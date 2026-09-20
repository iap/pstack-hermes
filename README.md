# Pstack Hermes

*Unofficial community port of Lauren Tan's **pstack** agent method for the
**Hermes Agent** plugin platform. Not affiliated with Cursor or Lauren Tan.
If you use Cursor, install the original instead:
<https://github.com/cursor/plugins/tree/main/pstack>.*

*Project slug: `pstack-hermes` · Package: `pstack` (upstream identity, v0.14.8) ·
Upstream pinned at `93b00b8` (MIT).*

**What this project is:** the Hermes integration, adjustment, and compatibility
layer for pstack — a self-contained `agent-plugins-v1` package plus the
converter/validator tooling that keeps it faithful to upstream. **What it is
not:** a Cursor plugin, a fork of the Cursor plugins repo, or the place to
report upstream Cursor issues. Port problems belong here (Issues); original
Cursor-plugin bugs that reproduce without this port belong upstream.

## Install

```sh
# hermes (portable plugin path) — root install (recommended)
hermes plugins install iap/pstack --enable

# Legacy: subdir install from this dev repo (still works)
hermes plugins install iap/pstack-hermes/pstack --enable
```

> [!NOTE]
> The root form installs from the **dist repo** (`iap/pstack`), whose tree root
> is the built package — published by CI from the pinned upstream build
> ([publish-plugin.yml](.github/workflows/publish-plugin.yml)). The dev repo
> itself (`iap/pstack-hermes`) cannot be installed from its root: the install
> scanner scans the whole tree, and this repo deliberately ships its
> development tooling (`tools/`, CI) alongside the package. The `pstack` subdir
> is the plugin; the dist repo is the plugin.

> [!NOTE]
> The bare-name form `hermes plugins install pstack` is not available —
> the package has no entry in the hermes plugin catalog yet. Use one of the
> two forms above.

**Update:** a root install keeps `.git`, so it updates in-place:
```sh
hermes plugins update pstack
```

Subdir installs strip the `.git` directory on install and cannot update
in-place — to update one, uninstall and reinstall with the subdir form.

## What's inside

- **45 skills** (24 workflow/mode + 21 `principle-*`) — the full method:
  `poteto-mode` router, verification playbooks, interrogation/reflect/recall
  loops, swarm/arena parallel workflows, and the principle library.
- **hermesbot** fills the excluded `make-bot-ui` slot: a hermes-native
  control-surface skill (webhook-waked UI) on the hermes gateway's own
  webhook (`X-Webhook-Signature-V2` HMAC), `hermes send`, and `hermes peer`
  stack — no Tailscale, no third-party bot runtime.
- **Hermes-native rewrites**: delegation translated to hermes `delegate_task`
  (all Cursor `Task`/`subagent_type`/`run_in_background` vocabulary removed),
  discovery rewritten to hermes-native `session_search`/`session` tools,
  config shipped as hermes `config/models.json`.
- **setup-pstack onboarding flow** adapted for hermes profiles and `config/models.json`.

## Repository layout

```
AGENTS.md          instructions for coding agents (triage, hermes work loop, vocabulary)
pstack/            the built package (converter output; provenance in .build-provenance.txt)
tools/convert.py   Cursor pstack → hermes converter (anchor-audited transform passes, atomic builds)
tools/validate.py  verification ladder: static (incl. bans + hermes adaptation contract) → repo YAML
                   → gold manifest → gold load
patches/           historical hermes-fork patches (reference only; not required to install)
docs/              ADAPTATIONS.md (the ledger), RUNBOOK-upstream-drift.md, USING.md,
                   PATCHES.md + UPSTREAM-PR.md (historical)
.github/           CI (ci.yml: 2-OS matrix, SHA gates, determinism, poteto-mode Bun suite),
                   publish-plugin.yml (dist-repo publisher), PR labeler, issue templates
```

## Verification

`tools/validate.py` runs a four-stage ladder and exits non-zero on any hard
failure:

1. **Static** — manifest schema, skill structure, encoding (LF-only, no BOM),
   publisher contract (excluded upstreams absent), banned-construct scan.
2. **Repo YAML** — every `.github` YAML file parses (when pyyaml is available,
   e.g. `uv sync`).
3. **Gold manifest** — the real hermes loader parses the manifest, zero
   diagnostics.
4. **Gold load** — the real loader discovers all skills, zero component
   diagnostics.

CI additionally enforces: the **pinned upstream SHA** (re-checked after clone),
**provenance consistency** (`source_commit` == pinned SHA), the scanner-clean
invariant set (`tools/bans.py`, scanned across every UTF-8-decodable file),
byte-reproducible builds (`SOURCE_DATE_EPOCH`), and unit tests + lint
(`pytest` + `ruff`) for the tooling itself. A weekly
[upstream-drift-watch](.github/workflows/upstream-drift-watch.yml) workflow
opens a tracking issue when upstream `pstack/` changes past the pin, and a
weekly [model-drift-watch](.github/workflows/model-drift-watch.yml) workflow
re-verifies every configured model slug against the provider catalog.

## Development

```sh
uv sync          # pinned CPython 3.11 + dev group (pyyaml, pytest, ruff)
uv run --frozen tools/convert.py  --source <pstack-clone> --out pstack
uv run --frozen tools/validate.py
uv run --frozen pytest -q             # tooling unit tests
uv run --frozen ruff check tools      # lint
```

The poteto-mode checker scripts additionally run a Bun suite (CI runs the
same): `cd pstack/skills/poteto-mode/scripts && bun run test && bun run typecheck`.

Coding agents start with [AGENTS.md](AGENTS.md) (triage + hermes verify loop);
humans continue in [CONTRIBUTING.md](CONTRIBUTING.md) for procedures, and
[docs/PATCHES.md](docs/PATCHES.md) for historical hermes-fork patch reference.

## Naming

| Thing | Name | Why |
|---|---|---|
| The package | `pstack` | upstream identity (plugin.json, v0.14.8) — preserved |
| This repository | `pstack-hermes` | the project slug and published repo name (docs title: Pstack Hermes); the development/pipeline repo |
| Dist repo | `pstack` (`iap/pstack`) | plugin-only build output, published by [publish-plugin.yml](.github/workflows/publish-plugin.yml) (append-only commits); the root install source |
| Tooling project | `pstack-hermes-plugin-tools` | uv project scoping the converter/validator only |
| Repo releases | `v0.4.x` | tooling/CHANGELOG version line — a release never renumbers the package, which keeps the upstream pstack version (`0.14.8`) |
| Plugin namespace | `agent-plugin-pstack-7171b73f:<skill>` | hermes portable-path id (derived from the manifest) |

## Cursor dual-load (incidental, unsupported)

`.cursor-plugin/plugin.json` is preserved unchanged, so this same directory still
loads as a Cursor plugin structurally — but the skills' *content* is fully
hermes-adapted and Cursor-side behavior is neither tested nor supported here.
For real Cursor-side work, install upstream pstack instead. The
`.cursor-plugin/` and `agents/` surfaces are inert on hermes.

## Known limitations

- **Graphite (`gt`) optional** — poteto-mode's `orch` now defaults to
  GitHub-native stack discovery (`gh pr list` base/head chain). Graphite
  is still supported via `--provider graphite` but is no longer required.
- **Cloud restacks** — restacking still requires Graphite (`gt`); hermes
  runs lanes locally via `git rebase` + `git push --force-with-lease`.
- **Cursor control surfaces** — `control-ui`, `control-cli`, and `deslop`
  are Cursor-only skills with no hermes equivalent. Live UI/CLI
  verification is not available on hermes.
- **Origin forge** — `origin pr ...` commands are Cursor's Origin CLI;
  hermes falls back to `gh` when Origin is not installed.

## License

MIT — upstream © 2026 Lauren Tan; port modifications © 2026 the
pstack-hermes-port contributors. See [LICENSE](LICENSE).
