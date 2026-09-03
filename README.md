# Pstack Hermes

*Project slug: `pstack-hermes` · Package: `pstack` (upstream identity, v0.14.4)*

**pstack** — Lauren Tan's rigorous, deeply-methodical agent engineering method
("if you want to go fast, go deep first") — ported to the **Hermes Agent**
platform as a self-contained `agent-plugins-v1` package.

Upstream: <https://github.com/cursor/plugins/tree/main/pstack> ·
pstack v0.14.4 · MIT · pinned at upstream commit `799151d`.
This port is platform-neutral: the package has **no Cursor runtime dependency**
and dual-loads on Cursor unchanged.

## Install

```sh
# hermes (portable plugin path) — verified subdir flow (scanner-clean)
hermes plugins install iap/pstack-hermes/pstack --enable
```

Once the plugin-index entry merges, the bare-name form also works:
`hermes plugins install pstack`.

> Note: installing from the repo root or the release zip URL is blocked by the
> install scanner **by design** — this repository ships its development tooling
> (`tools/`, CI) alongside the package, and the scanner correctly refuses to
> install a source tree that contains it. The `pstack` subdir is the plugin.

Cursor (dual-load, optional): point Cursor at the package root — the
`.cursor-plugin/plugin.json` and `agents/` surfaces are inert on hermes.

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
pstack/            the built package (converter output; provenance in .build-provenance.txt)
tools/convert.py   Cursor → hermes converter (T1–T11 transforms, atomic builds)
tools/validate.py  verification ladder: static → repo YAML → gold loader → doctor
patches/           the 4 hermes-fork patches the port depends on
docs/              PATCHES.md (fork patch docs), UPSTREAM-PR.md (drafted PR)
.github/           CI (ci.yml: 2-OS matrix, SHA gates, determinism), PR labeler, issue templates
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
invariant set, and byte-reproducible builds (`SOURCE_DATE_EPOCH`).

## Development

```sh
uv sync          # pinned CPython 3.11 + dev group (pyyaml)
uv run --frozen tools/convert.py  --source <pstack-clone> --out pstack
uv run --frozen tools/validate.py
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full contract, and
[docs/PATCHES.md](docs/PATCHES.md) for the fork patches the port relies on.

## Naming

| Thing | Name | Why |
|---|---|---|
| The package | `pstack` | upstream identity (plugin.json, v0.14.4) — preserved |
| This repository | `pstack-hermes` | the project slug and published repo name (docs title: Pstack Hermes) |
| Tooling project | `pstack-hermes-plugin-tools` | uv project scoping the converter/validator only |
| Plugin namespace | `agent-plugin-pstack-7171b73f:<skill>` | hermes portable-path id (derived from the manifest) |

## License

MIT — upstream © 2026 Lauren Tan; port modifications © 2026 the
pstack-hermes-port contributors. See [LICENSE](LICENSE).
