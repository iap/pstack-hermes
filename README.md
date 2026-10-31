<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:b2eea8f645abfccabfe4ae3e7cda81459321f7fb0792cb57400dda0b8fea4cd4 -->

<!-- coderabbit-ai-generated-section:v1:9fb4e5defbb115d04501de70d9817104330be2ee94ce15585eede94a81dc0bff -->

<!-- coderabbit-ai-generated-section:v1:d94993548a48265942779aa3b7ed36972c0efe779eac4698d96dec3e7e91be3d -->

# pstack

*The pstack agent method as a **native Hermes Agent plugin installation** —
an unofficial community port of Lauren Tan's
[pstack](https://github.com/cursor/plugins/tree/main/pstack). Not affiliated
with Cursor or Lauren Tan; if you use Cursor, install the original instead.*

*Project slug: `pstack-hermes` · Package: `pstack` (upstream identity, v0.15.5) ·
Upstream pinned at `c47b1284` (MIT).*

**What this project is:** a native hermes plugin — a self-contained
`agent-plugins-v1` package published on the `dist` branch and installed and
updated through `hermes plugins`, plus the converter/validator tooling that
keeps it faithful to upstream. **What it is not:** a Cursor plugin, a fork of
the Cursor plugins repo, or the place to report upstream Cursor issues. Port
problems belong here (Issues); original issues that reproduce without this
port belong upstream.

## Install

Project name: **pstack**. Repository slug: **pstack-hermes**.
<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:c8ad5ea2d621eebf4b7c170b4a8cf3fddc86b5f1b8ffb1228b7921cb88cc51b7 -->

`iap/pstack` is not an alias for this repository.

<!-- /coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:98a82daec2a7d8a4fc98b909af902a35857ceb0f945f32164332d0d1d7a0db0d -->

Choose the command for the current default branch shown on the
[repository page](https://github.com/iap/pstack-hermes). During the migration
it may be `dist` or `master`.

If the default branch is `dist`, install the package at the repository root:

```sh
hermes plugins install iap/pstack-hermes --enable
```

If the default branch is `master`, install the generated subdirectory:

```sh
hermes plugins install iap/pstack-hermes/pstack --enable
```

Both unpinned installs update with `hermes plugins update pstack`. Existing
`dist` clones remain on `dist` after the default branch changes.

<!-- /coderabbit-ai-generated:v1 -->

For an immutable root install, copy the full **package commit SHA** from a
[GitHub Release](https://github.com/iap/pstack-hermes/releases):

```sh
hermes plugins install iap/pstack-hermes --ref <40-character-package-SHA> --enable
```

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:e990c9712b2761e42609a0edfb94c0387baa376730e6e796f945bdc64cf45e3a -->

Pinned installs do not auto-update. To move an existing pin, explicitly
replace the installed plugin with a newer package SHA:

```sh
hermes plugins install iap/pstack-hermes --ref <new-package-SHA> --force --enable
```

<!-- /coderabbit-ai-generated:v1 -->
The `dist` compatibility branch remains append-only. Release ZIPs contain
`pstack/`; use the immutable Git SHA command above for installation.

## Project tracking

Use [issues](https://github.com/iap/pstack-hermes/issues) for proposals,
adaptations, decisions, acceptance criteria and verification; use native
sub-issues for bounded implementation work and milestones for delivery goals.
The preserved [adaptation register](https://github.com/iap/pstack-hermes/issues/94)
records existing port contracts. Documentation holds maintained instructions.

## What's inside

- **47 skills** (24 workflow/mode + 23 `principle-*`) — the full method:
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
- **setup-pstack onboarding flow** adapted for hermes profiles and external
  model-panel storage (survives plugin updates). The upstream-name →
  hermes-default model mapping is documented in [docs/MODELS.md](docs/MODELS.md).

## Repository layout

```
AGENTS.md          instructions for coding agents (triage, write surface, vocabulary)
pstack/            the built package (converter output; provenance in .build-provenance.txt)
tools/convert.py   Cursor pstack → hermes converter (anchor-audited transform passes, atomic builds)
tools/validate.py  verification ladder: static (incl. bans + hermes adaptation contract) → repo YAML
                   → gold manifest → gold load
patches/           historical hermes-fork patches (reference only; not required to install)
docs/              operational, usage and development instructions (see docs/AGENTS.md)
.github/           CI (ci.yml: 2-OS matrix, SHA gates, determinism, poteto-mode Bun suite),
                   publish-dist.yml (dist-branch publisher), PR labeler, issue templates
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

Coding agents start with [AGENTS.md](AGENTS.md) (triage + write surface +
hermes verify loop); humans continue in [CONTRIBUTING.md](CONTRIBUTING.md) for
procedures, and [docs/PATCHES.md](docs/PATCHES.md) for historical hermes-fork
patch reference. End-user invoke and customization:
[docs/USING.md](docs/USING.md).

## Naming

| Thing | Name | Why |
|---|---|---|
| The package | `pstack` | upstream identity (plugin.json, v0.15.5) — preserved |
| This repository | `pstack-hermes` | the project slug and published repo name; project name is pstack |
| Dist branch | `dist` (this repo) | plugin-only compatibility build output, published by [publish-dist.yml](.github/workflows/publish-dist.yml) (append-only); the install source — no second repository |
| Tooling project | `pstack-hermes-plugin-tools` | uv project scoping the converter/validator only |
| Repo releases | `v0.4.x` | tooling/CHANGELOG version line — a release never renumbers the package, which keeps the upstream pstack version (`0.15.5`) |
| Plugin namespace | `agent-plugin-pstack-7171b73f:<skill>` | hermes portable-path id (derived from the manifest) |

## Heritage layout (inert on hermes)

A `.cursor-plugin/plugin.json` is preserved for provenance from the upstream
tree; the `.cursor-plugin/` and `agents/` surfaces are inert here — the package
is a hermes plugin, the skills' content is hermes-adapted, and Cursor-side
behavior is neither tested nor supported. For Cursor-side work, install
upstream pstack instead.

## Known limitations

- **Stack forge** — **Graphite (`gt`) is the default** when available; **GitHub
  (`gh`)** is the fallback (PR base/head topology). **GitLab (`glab`) is not
  implemented** (halted). Missing Graphite is not a hard failure when GitHub
  can complete the task; some restack/stack-surgery paths still need `gt`.
- **Cloud restacks** — full Graphite cloud restack behavior is not mirrored;
  hermes runs lanes locally via `git rebase` + `git push --force-with-lease`
  where applicable.
- **Cursor control surfaces** — `control-ui`, `control-cli`, and `deslop`
  are Cursor-only skills with no hermes equivalent. Live UI/CLI
  verification is not available on hermes.
- **Origin forge** — `origin pr ...` commands are Cursor's Origin CLI;
  hermes falls back to `gh` when Origin is not installed.
- **Stock skills vs learning** — Hermes self-improvement must not target stock
  plugin skills as durable source of truth; use a skill tap, a dist fork, or
  local skills ([docs/USING.md](docs/USING.md)).

## License

MIT — upstream © 2026 Lauren Tan; port modifications © 2026 the
pstack-hermes-port contributors. See [LICENSE](LICENSE).


<!-- /coderabbit-ai-generated:v1 -->