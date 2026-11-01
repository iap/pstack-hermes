<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:42b6141d38bacc37685835b7e9b858945dfa08a0743f5c7fe61c096a1dd30784 -->

<!-- coderabbit-ai-generated-section:v1:ebc283da134d7475cca68f35bb3583ad31c7e109d1b7de7f8bf52001bc95c7a6 -->

<!-- coderabbit-ai-generated-section:v1:f07db69766104967cc27b575968211c722f833bde62f42f3048e74bdde0d0575 -->

<!-- coderabbit-ai-generated-section:v1:e35bc2f6b95555feb97dcf319b0170b52dcd6e40c6e8aa7b01ff69a5e847b288 -->

<!-- coderabbit-ai-generated-section:v1:4d11144e6dca943b2c50a4192621fb844dce6ac8084b9f6b30a976eb3574d2a9 -->

# Contributing

Thanks for helping port and maintain pstack on hermes. The repo is small and
the contract is strict — read this once and the CI will never surprise you.

> [!NOTE]
> Coding agents start at [AGENTS.md](AGENTS.md) (always-on contract) and open
> one row in [docs/agent/](docs/agent/README.md) for deep ops. Humans start
> here. CONTRIBUTING wins on authoring and release procedure; AGENTS wins on
> how to work in the repo.

## Orientation

| Read | For |
|---|---|
| [AGENTS.md](AGENTS.md) | always-on triage, hard contracts, traps |
| [docs/agent/](docs/agent/README.md) | job-routed deep ops (layout, convert/adapt, re-pin, bot review) |
| [README.md](README.md) | project identity, install, verification summary |
| [adaptation register](https://github.com/iap/pstack-hermes/issues/94) | ledger: every conversion pass and its reviewer check |
| [docs/PATCHES.md](docs/PATCHES.md) | historical hermes-fork patches (reference only) |

One-sentence model of the repo: **`tools/convert.py` generates the plugin
package into the repository root; `tools/validate.py` and CI keep that output
honest; everything hand-written exists to serve that pipeline.**

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
cd skills/poteto-mode/scripts
bun run test                              # deps + `bun test orch watch-pr`
bun run typecheck                         # deps + tsc --noEmit --strict
```

## Pipeline and package contract

Convert → validate → doctor → publish is documented once in
[docs/agent/convert-adapt.md](docs/agent/convert-adapt.md) (layout:
[docs/agent/layout.md](docs/agent/layout.md)). Humans: run **Setup** above
before editing; agents follow AGENTS + the convert-adapt work loop.

- Target `master` for development PRs; keep `dist` append-only.
- Generated package surfaces are never hand-edited (see layout).
- Banned constructs: `tools/bans.py` + `HERMES_ADAPTATION_BANS` in
  `validate.py` (enforced by validate + `scanner_gate.py`). Legacy model
  slugs kept as fallback documentation in skill prose are intentional.
- Encoding: LF-only, no BOM.
- Port work © pstack-hermes-port contributors.
- Fork patches: [docs/PATCHES.md](docs/PATCHES.md); historical upstream PR
  proposal: [#95](https://github.com/iap/pstack-hermes/issues/95).

## GitHub Actions & workflow policy

The `.github/` tree is hand-written and gated; these rules exist because each
one has already caught (or would have caught) a real defect here.

- **Every action is pinned to a full commit SHA** with a trailing `# vN`
  comment. `dependabot.yml` keeps them current: the weekly `github-actions`
  group PR updates both the SHA and the comment. Review SHA bumps like any
  dependency change - the usual CI gates run on the PR. The root entry does
  **not** cover `.github/actions/*/action.yml`, so each composite action with
  its own `uses:` needs a directory-scoped entry there.
- **The repository Actions allowlist is closed.** Settings -> Actions permits
  GitHub-owned actions plus the `astral-sh/setup-uv@*` and `oven-sh/setup-bun@*`
  patterns only, with `sha_pinning_required` on and a read-only default
  `GITHUB_TOKEN` (the policy lives in repository settings, not in this tree).
  A new third-party action fails at `Set up job` with "not allowed" until its
  `owner/repo` is added there - deliberately, so introducing an action is a
  decision rather than an accident. Dependabot keeps already-allowed pins
  current as usual.
- **`UPSTREAM_PIN` moves in lock-step.** It is declared in `ci.yml`,
  `release.yml`, and `publish-dist.yml`;
  `tools/check_pins.py` fails CI when any required declarer is missing,
  duplicated, malformed, or out of step. Follow
  [docs/agent/upstream-drift.md](docs/agent/upstream-drift.md).
- **Workflows must pass `actionlint`** (with `shellcheck`) - the `Lint
  workflows` CI step, runnable locally as `uv run --frozen actionlint`.
- **Action inputs must be declared by the action they target.** `tools/`
  `check_action_inputs.py` fails on a `with:` key the pinned action does not
  declare - the runner only warns and silently ignores such a key (the
  `syncLabels` / `sync-labels` defect), and actionlint cannot see it because it
  does not read remote action metadata.
- **Composite actions must pass `tools/check_action_shell.py`.** actionlint
  does not lint `.github/actions/*/action.yml` steps, so that file's run
  blocks get their own shellcheck pass in CI. If the gate flags something,
  fix it or add a targeted `# shellcheck disable=` with a comment saying why
  (see `drift-issue-upsert` for the jq `$ENV` case).
- **Reuse: composite action when callers continue afterwards; reusable
  workflow only when the shared thing is a whole job.** Both call sites and
  the rationale are documented in `.github/actions/build-package/action.yml`.
  Shared multi-step logic (build prologue, drift-issue upsert) lives in
  `.github/actions/`, and no workflow re-inlines it.
- **Minimal `permissions:` at workflow level**, widened only per job where a
  step needs it. Checkouts that never push set `persist-credentials: false`.
- **Every job sets `timeout-minutes`.** A hung step otherwise burns the
  6-hour default before anyone notices.
- **`pull_request_target` is allowed only for the labeler**, where no PR
  content is checked out or executed. Never add a PR-head checkout to that
  job; put such work in a `pull_request` workflow instead.

## Common tasks

Converter transforms, model panel, hermesbot, and verify:
[docs/agent/convert-adapt.md](docs/agent/convert-adapt.md).

Re-pin upstream:
[docs/agent/upstream-drift.md](docs/agent/upstream-drift.md)
(`UPSTREAM_PIN` lock-step enforced by `tools/check_pins.py`).

### Release

1. Merge the release changes to `master`, including the `CHANGELOG.md`
   section for the `v0.5.x` tooling version. Package version stays upstream's.
2. Wait for `publish-dist` to succeed. Create a `v*` tag on that source commit.
3. `release.yml` rebuilds and validates, checks that the package matches the
<!-- coderabbit-ai-generated:v1 -->
<!-- coderabbit-ai-generated-section:v1:9ad9535da30d31f95f6f7b2099158d95227e5463771f36b895a4222c9dcb07df -->
   published `dist` commit, including provenance except `converted_at`, and
   creates a GitHub Release with ZIP, SHA-256 checksum, source SHA and immutable
   package install command.
<!-- /coderabbit-ai-generated:v1 -->
   A lagging or different dist tree fails release creation; rerun after publish.
4. Close the milestone once all acceptance checks pass. Link issues and PRs
   in release notes. Never move an existing release tag.

### Plan and adaptation tracking

Create issues for proposals, implementation plans and adaptation decisions.
Each includes motivation, scope, acceptance criteria and reviewer checks.
Split independent work into native sub-issues and use milestones for outcomes.
A converter PR links its adaptation issue and includes the generated package;
retain the [existing contracts](https://github.com/iap/pstack-hermes/issues/94).
Do not keep parallel plans or adaptation ledgers in `docs/`.

## Pull requests

The [PR template](.github/PULL_REQUEST_TEMPLATE.md) requires: convert clean,
validate exit 0, doctor exit 0 (install-relevant), banned-construct scan, the
poteto-mode Bun suite (`bun run test` / `bun run typecheck`), provenance
consistency. A PR that changes generated package surfaces must say
`rebuilt from pin <sha>` in its body and name the converter change behind the
rebuild — reviewers read that tree as build output. CI runs the suite plus the
pinned-SHA reproducibility check, unit tests, lint, and a weekly
[model-drift-watch](.github/workflows/model-drift-watch.yml) that re-verifies
configured model slugs (`tools/slug_drift.py`). PRs are auto-labeled by path
(labels via `labels-bootstrap`).

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
- **Generated package surfaces** (`skills/`, `config/`, package `README.md`,
  …). Rebuilt by `tools/convert.py` from upstream and never hand-edited.
  Don't add a callout convention there as a hand-edit rule — it would be wiped
  on the next build. If alerts belong in package prose, that's a converter
  change (and an upstream-drift consideration), not a CONTRIBUTING note.


<!-- /coderabbit-ai-generated:v1 -->