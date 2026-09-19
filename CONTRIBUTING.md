# Contributing

Thanks for helping port and maintain pstack on hermes. The repo is small and
the contract is strict — read this once and the CI will never surprise you.

> [!NOTE]
> Coding agents work from [AGENTS.md](AGENTS.md) (change triage, hermes work
> loop, vocabulary bans). Humans start here. Both describe the same contract;
> that file carries triage and verification orientation; this file carries
> procedures (setup, common tasks, PRs, release).

## Orientation

| Read | For |
|---|---|
| [AGENTS.md](AGENTS.md) | triage (this repo vs hermes vs upstream), work loop, hermes verify, vocabulary |
| [README.md](README.md) | project identity, install, verification summary, naming table |
| [docs/ADAPTATIONS.md](docs/ADAPTATIONS.md) | the ledger: every conversion pass and its reviewer check |
| [docs/RUNBOOK-upstream-drift.md](docs/RUNBOOK-upstream-drift.md) | re-pinning procedure when upstream moves |
| [docs/PATCHES.md](docs/PATCHES.md) | historical hermes-fork patches (reference only; not required to install) |

One-sentence model of the repo: **`tools/convert.py` turns a pinned upstream
clone into `pstack/`; `tools/validate.py` and CI keep that output honest;
everything hand-written exists to serve that pipeline.**

## Setup

```sh
uv sync                                   # pinned CPython 3.11 + dev group (pyyaml, pytest, ruff)
uv run --frozen tools/validate.py         # must exit 0 before you start
uv run --frozen pytest -q                 # unit tests for the tooling
uv run --frozen ruff check tools          # lint
```

Python is pinned via `.python-version` and `uv.lock`; never commit interpreter
or dependency drift.

The poteto-mode checker scripts additionally need
[Bun](https://bun.sh) (CI runs the same suite):

```sh
cd pstack/skills/poteto-mode/scripts
bun run test                              # deps + `bun test orch watch-pr`
bun run typecheck                         # deps + tsc --noEmit --strict
```

## The pipeline

1. **Convert** — `tools/convert.py` rebuilds `pstack/` from any pstack clone
   (or a fresh upstream clone at the pinned SHA). Builds are atomic
   (`pstack.tmp-build` swap, with rollback if the swap fails) and
   byte-reproducible under `SOURCE_DATE_EPOCH`. Every transform anchor in the
   T8/T9/T10/T11/delegation maps is audited: an anchor that matches nothing in
   the upstream build fails the build loudly (upstream drift must be resolved
   by updating or pruning the map, never ignored).
2. **Validate** — `tools/validate.py` runs the four-stage ladder (static →
   repo YAML → gold manifest → gold load). The static stage includes the
   **hermes adaptation contract** (no inert `persona:` blocks, no stale
   runtime claims, no Cursor tool names, no transcript paths, no cloud-worker
   wording, no Cursor-style auto selectors in shipped skills), the
   banned-construct scan, and the model-panel checks (panel == shipped
   `config/models.json`, provider-qualified slugs, per-role value shapes,
   no duplicate concrete slugs inside an array role). The expected skill
   count is **derived from the package**, not hardcoded — structural changes
   flow through automatically. Dependency installs (`node_modules/`) created
   by script verification are exempt from the scans.
3. **Doctor** — `hermes plugins doctor pstack --ci` for install-relevant
   changes (maintainer machine; needs the hermes venv).
4. **Publish** — on every push to `main`,
   [publish-plugin.yml](.github/workflows/publish-plugin.yml) re-runs
   convert → validate → scanner gate and publishes the built tree to the
   dist repo `iap/pstack` as an **append-only commit**, tagged
   `pstack-<date>-<sha>` (the plugin catalog admits only repos with real
   tags). Build output: never edited by hand, history never rewritten —
   `hermes plugins update` fast-forwards installed clones. The dist
   repo's tree root is the package, which is what makes the root install
   shorthand (`hermes plugins install iap/pstack`) and in-place
   `hermes plugins update pstack` work. Requires the one-time `PLUGIN_DIST_TOKEN`
   secret (fine-grained PAT, contents: read/write on the dist repo only).

## Repository contract

- `pstack/` is **generated content** — never hand-edit; change the converter
  and rebuild. Provenance (`.build-provenance.txt`) must record the pinned
  upstream SHA at all times.
- **Banned constructs** are defined once in `tools/bans.py` (6 delegation tokens: `subagent_type`, `generalPurpose`, `AskQuestion`, `` `Task` ``, `run_in_background`, `environment: "cloud"`, plus 3 security needles: `tailscale.com/install.sh`, `FOR_AGENTS.md`, `http://127.0.0.1:4173`) and the hermes adaptation bans in `tools/validate.py`. Enforced by `tools/validate.py` and the CI scanner gate (`tools/scanner_gate.py`). Inline legacy model slugs in skill prose (e.g. the `PSTACK_FAST_LANE` default) are intentional fallback documentation, not banned.
- Encoding: LF-only, no BOM (`.gitattributes` enforces; validate.py fails on
  drift).
- Attribution: upstream MIT (© Lauren Tan) is preserved everywhere; new port
  work is © the pstack-hermes-port contributors.
- Fork patches live in `patches/` with documentation in
  [docs/PATCHES.md](docs/PATCHES.md); the drafted upstream PR text is
  [docs/UPSTREAM-PR.md](docs/UPSTREAM-PR.md).

## Common tasks

### Add or change a converter transform

1. Edit the map or pass in `tools/convert.py` (maps like `T8_MAP`,
   `DELEGATION_MAP`; passes register in `st.fixes`).
2. Rebuild: `uv run --frozen tools/convert.py --source <pstack-clone> --out pstack`
   — a dead anchor fails here on purpose.
3. Add a row to [docs/ADAPTATIONS.md](docs/ADAPTATIONS.md) (pass, what it
   changes, source of truth, **reviewer check**). A row without a reviewer
   check is a claim, not documentation.
4. If the pass has a checkable scope, add a unit test
   (`tools/tests/test_t11_scope.py` is the pattern).
5. `uv run --frozen tools/validate.py` and the full local suite, then PR with
   the rebuilt tree and `rebuilt from pin <sha>` in the body.

### Re-pin upstream

Follow [docs/RUNBOOK-upstream-drift.md](docs/RUNBOOK-upstream-drift.md)
verbatim. The one rule people forget: `UPSTREAM_PIN` is declared independently
in **three workflows** — `ci.yml`, `release.yml`, `upstream-drift-watch.yml` —
and all three must move in the same PR. Update maps, never the package.

### Change the model panel

Edit `tools/assets/model-panel.json` (never the shipped
`pstack/config/models.json` — Stage-D copies it in and `validate.py` checks
they match). Rebuild, then confirm the weekly
[model-drift-watch](.github/workflows/model-drift-watch.yml) assumptions still
hold: slugs are provider-qualified `vendor/model[:variant]`, array roles hold
no duplicate concrete slugs, and per-role value shapes (string vs array)
match the converter's expectations. Prose-only slug mentions are
informational (`tools/slug_drift.py --prose`).

### Update hermesbot

Edit `tools/assets/hermesbot/SKILL.md` — the shipped
`pstack/skills/hermesbot/` copy is converter output. Rebuild and validate.

### Release

1. Add the `CHANGELOG.md` section for the new `v0.4.x` version (the repo
   release line; the package itself keeps the upstream `0.14.8` and is never
   renumbered).
2. Tag `v*`; [release.yml](.github/workflows/release.yml) rebuilds from the
   pin, validates, runs the scanner gate, zips `pstack-<version>.zip`, and
   writes the release body from the CHANGELOG section.
3. Nothing is built locally for a release — the workflow is the only
   publisher.

## Pull requests

The [PR template](.github/PULL_REQUEST_TEMPLATE.md) requires: convert clean, validate
exit 0, doctor exit 0 (install-relevant), banned-construct scan, the
poteto-mode Bun suite (`bun run test` / `bun run typecheck`), provenance
consistency. A PR that changes `pstack/` must say `rebuilt from pin <sha>` in its
body and name the converter change behind the rebuild — that tree is build
output, and reviewers read it as output. The [PR template](.github/PULL_REQUEST_TEMPLATE.md)
carries the matching "Generated package" fields. CI runs all of it plus the pinned-SHA re-check, unit tests, lint,
and a weekly upstream-drift check
([upstream-drift-watch](.github/workflows/upstream-drift-watch.yml)) that opens
a tracking issue when upstream `pstack/` changes past the pin; a weekly
[model-drift-watch](.github/workflows/model-drift-watch.yml) re-verifies every
configured model slug against the provider catalog (`tools/slug_drift.py`).
PRs are
auto-labeled by path (labels are created once via the `labels-bootstrap`
workflow after the repo goes public).

## Issue reports

Use the templates — platform (hermes portable / hermes slash / Cursor
dual-load) and affected skill are required fields; `hermes plugins doctor
pstack --ci` output is the most useful evidence you can attach.

## Document style

GitHub renders **alert callouts** in markdown, so use them in this repo's
hand-written docs (`CONTRIBUTING.md`, `README.md`, `SECURITY.md`, the PR
template, issue bodies). They carry more weight than a plain `> Note.` block.

```
> [!NOTE]
> Required context, or a non-obvious "yes, this is intended".

> [!IMPORTANT]
> A decision or constraint that changes what a correct change looks like.

> [!WARNING]
> Something that will silently break or mislead if skipped.

> [!TIP]
> A shortcut worth knowing, not required for correctness.
```

- One callout per point. Don't stack them; write the prose instead.
- `[!CAUTION]` is for *destructive or irreversible* steps — use it sparingly,
  and only where a reader could actually hit the action.
- Keep the first line short; the body carries the detail. GitHub truncates
  callouts to a preview in some views.

### Where alerts do **not** apply

- **Commit messages.** GitHub does not render markdown (including alerts) in
  commit messages — they stay plain text. Say it in the subject line or the
  body as normal prose. The `type(scope): summary` convention already carries
  the what/why; add a second line for the why if it doesn't fit.
- **The generated `pstack/` package.** That tree is rebuilt by
  `tools/convert.py` from upstream and is never hand-edited. Don't add a
  callout convention there as a hand-edit rule — it would be wiped on the next
  build. If alerts belong in package prose, that's a converter change (and an
  upstream-drift consideration), not a CONTRIBUTING note.
