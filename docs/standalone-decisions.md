# Standalone project decisions (issue #160)

Decisions locked before the standalone refactor touches code. Each entry states the decision, why, and what it unblocks. These are inputs to sub-issues #157 (vocabulary), #158 (poteto extract), and #159 (agent instructions).

> [!NOTE]
> This file is hand-written and durable. Later PRs point here instead of re-litigating these calls.

## 1. Package identity — name stays `pstack`

> [!IMPORTANT]
> The install noun stays `pstack`. `plugin.json` `name` remains `"pstack"`; directory, `hermes plugins doctor pstack`, and existing installs are unaffected.

Rationale: renaming the package now would churn every install, doc reference, and the `dist` channel for zero user benefit. Revisit only if the project later wants to field its own brand — at that point both `plugin.json` and the `dist` channel move together.

## 2. `plugin.json` version — locally owned

> [!IMPORTANT]
> Version `0.15.5` is the last upstream version. From the first standalone release, `plugin.json` `version` is owned by this repo.

Policy:

- **Minor** (`0.16.0`) — new skills, new tools, new playbooks.
- **Patch** (`0.15.6`) — fixes, vocabulary corrections, doc fixes that ship in the package.
- **Major** (`1.0.0`) — one-way function: only when a standalone breaking change lands (e.g. skill removal or invocation-path changes).

Bump the version in the same PR as the change that justifies it. `CHANGELOG.md` records the mapping (version → change) for every bump.

## 3. Poteto tooling — `@iap/poteto`, extracted to `tools/poteto/`

> [!IMPORTANT]
> Confirmed: the extracted tooling package is named `@iap/poteto` and lives at `tools/poteto/`.

Rationale: `tools/` keeps tooling discoverable next to the rest of the repo tooling; the scoped `@iap/` name is the maintainer's org scope. `skills/poteto-mode/scripts/` is deleted on extraction; `SKILL.md` references the new root-relative path.

## 4. README — hand-owned at the repo root

> [!IMPORTANT]
> `README.md` becomes a hand-written file. The converter's README template in `tools/convert.py` is deleted with the converter.

The README owns install, verification summary, and naming-table sections. Keep the existing sections; remove any "generated from upstream" framing.

## 5. LICENSE — standalone MIT, attribution intact

> [!IMPORTANT]
> `LICENSE` stays MIT. Upstream attribution (© Lauren Tan) is preserved; standalone additions are © the pstack-hermes-port contributors.

No license change. If the copyright-holder line wording needs alignment, that is a deliberate PR with a reviewer check — not a drive-by.

## 6. Provenance — rewritten standalone, then retired with the converter

Decision:

1. Rewrite `.build-provenance.txt` to a standalone provenance record (package name, version, built-from repo, final upstream SHA `c47b1284` recorded as historical context only).
2. Delete the upstream fields (`source_url`, `source_commit`, `converter`) — they describe a build path that no longer exists.
3. When the converter is dropped, remove `.build-provenance.txt` entirely if nothing reads it.

Final upstream SHA `c47b1284` is also recorded in `CHANGELOG.md` so the history survives the file.

## 7. Releases — unchanged dispatch

Signed-tag → `release.yml` from `master` → append-only `dist` channel stays as-is. The only change is that no step in the release path needs the upstream pin: remove `UPSTREAM_PIN` declarations and the reproducibility gate during the drop PR.

## 8. Workflow — `gt` stack for development

Development uses `gt` / `gt` stack; `gh` is fallback-only. That is the maintainer's local workflow and does not change any decision in this file.
