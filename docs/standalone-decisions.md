# Standalone project decisions (issue #160)

Decisions locked before the standalone refactor touches code. Each entry states the decision, why, and what it unblocks. These are inputs to sub-issues #157 (vocabulary), #158 (poteto extract), and #159 (agent instructions).

> [!NOTE]
> This file is hand-written and durable. Later PRs point here instead of re-litigating these calls.

## 1. Package identity — name stays `pstack`

> [!IMPORTANT]
> The install noun stays `pstack`. `plugin.json` `name` remains `"pstack"`; directory, `hermes plugins doctor pstack`, and existing installs are unaffected.

Rationale: renaming the package now would churn every install, doc reference, and the `dist` channel for zero user benefit. Revisit only if the project later wants to field its own brand — at that point both `plugin.json` and the `dist` channel move together.

**Manifest URLs.** `plugin.json` `homepage` and `repository` still point at `cursor/plugins`. Decision: keep them as upstream attribution until the brand decision lands; change them only in the brand PR, never as a drive-by.

## 2. `plugin.json` version — locally owned

> [!IMPORTANT]
> Version `0.15.5` is the last upstream version. From the drop PR onward, `plugin.json` `version` is owned by this repo.

**Effective when the converter is dropped.** Until then, `tools/convert.py` regenerates the root `plugin.json` from the upstream manifest on every run, so a hand-bumped version is reverted on the next rebuild and the reproducibility gate fails. The first standalone bump therefore lands in or after the drop PR — never before.

Policy:

- **Minor** (`0.16.0`) — new skills, new tools, new playbooks.
- **Patch** (`0.15.6`) — fixes, vocabulary corrections, doc fixes that ship in the package.
- **Major** (`1.0.0`) — one-way function: only when a standalone breaking change lands (e.g. skill removal or invocation-path changes).

Bump the version in the same PR as the change that justifies it. `CHANGELOG.md` records the mapping (version → change) for every bump.

> [!WARNING]
> Before the first standalone bump, update or retire the `NOTICE.md` ↔ `plugin.json` version check in `tools/check_pins.py` — left as-is, CI fails the standalone bump because the upstream notice still reads `0.15.5`. That update lands in the drop PR (see §7): the first standalone bump happens in or after the drop PR, so §2 and §7 share one timeline.

## 3. Poteto tooling — `@iap/poteto`, extracted to root

> [!IMPORTANT]
> Confirmed: the extracted tooling package is named `@iap/poteto` and lives at the repository root (`package.json`, `bun.lock`, and `scripts/`).

Rationale: the repo root keeps the Node tooling discoverable as a standard `package.json` workspace; the scoped `@iap/` name is the maintainer's org scope. `skills/poteto-mode/scripts/` is deleted on extraction; `SKILL.md` references the new root-relative path (`scripts/`).

**Distribution (required, part of the extraction PR).** The `dist` channel and release ZIP include `skills/` but not root tooling. Installed-package users depend on the shipped `orch` executable (Orchestrate playbook) and `watch-pr` launcher. The extraction PR must therefore route the tooling into distribution too — e.g. extend the dist publisher / release ZIP to copy `package.json`, `bun.lock`, and `scripts/` into the package, or keep a vendored copy under `skills/`. "Source lives at the root" alone ships a broken install.

## 4. README — hand-owned at the repo root

> [!IMPORTANT]
> **Effective when the converter is dropped.** From the drop PR, `README.md` is a hand-written file and the converter's README template in `tools/convert.py` is deleted. Until then, the generated-output rule in `AGENTS.md` and `CLAUDE.md` stands unchanged; sub-issue #159 updates those files in step with the drop.

The README owns install, verification summary, and naming-table sections. Keep the existing sections; remove any "generated from upstream" framing.

## 5. LICENSE — standalone MIT, attribution intact

> [!IMPORTANT]
> `LICENSE` stays MIT. Upstream attribution (© Lauren Tan) is preserved; standalone additions are © the pstack-hermes-port contributors.

No license change. If the copyright-holder line wording needs alignment, that is a deliberate PR with a reviewer check — not a drive-by.

## 6. Provenance — rewritten standalone, then retired with the converter

Decision (ordering matters):

1. **First, retire the gates that consume provenance fields.** `tools/pr_checklist.py`, `.github/PULL_REQUEST_TEMPLATE.md`, and the release provenance check in `.github/workflows/release.yml` still require `source_commit` and `converted_at` from `.build-provenance.txt`. Removing the fields before removing those checks breaks release and PR gating.
2. **Then, delete the upstream fields** (`source_url`, `source_commit`, `converter`) and rewrite `.build-provenance.txt` as a standalone record (package name, version, built-from repo, final upstream SHA `c47b1284` as historical context only) — **only in the drop PR, at the moment the converter is removed.** Before that point a converter rebuild regenerates the file with upstream fields, so any earlier rewrite is clobbered and could let release/dist publish a stale or upstream-flavored record.
3. **Then, when the converter is dropped, remove `.build-provenance.txt` entirely** if nothing reads it.

Gates first, fields second, file last — never the reverse.

Final upstream SHA `c47b1284` is also recorded in `CHANGELOG.md` so the history survives the file.

## 7. Releases — unchanged dispatch

Signed-tag → `release.yml` from `master` → append-only `dist` channel stays as-is. The only change is that no step in the release path needs the upstream pin: remove `UPSTREAM_PIN` declarations and the reproducibility gate during the drop PR.

**Pin checker (required, part of the drop plan).** CI runs `tools/check_pins.py`, which fails when the `UPSTREAM_PIN` declarations are absent. The drop PR must therefore update `tools/check_pins.py` in the same change — remove the upstream lockstep check so the standalone change does not block CI, while preserving the checker's separate Hermes pin and notice checks as appropriate.

## 8. Workflow — `gt` stack for development

Development uses `gt` / `gt` stack; `gh` is fallback-only. That is the maintainer's local workflow and does not change any decision in this file.
