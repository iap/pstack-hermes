# Contributing

Thanks for helping port and maintain pstack on hermes. The repo is small and
the contract is strict — read this once and the CI will never surprise you.

## Setup

```sh
uv sync                                   # pinned CPython 3.11 + dev group (pyyaml, pytest, ruff)
uv run --frozen tools/validate.py         # must exit 0 before you start
uv run --frozen pytest -q                 # unit tests for the tooling
uv run --frozen ruff check tools          # lint
```

Python is pinned via `.python-version` and `uv.lock`; never commit interpreter
or dependency drift.

## The pipeline

1. **Convert** — `tools/convert.py` rebuilds `pstack/` from any pstack clone
   (or a fresh upstream clone at the pinned SHA). Builds are atomic
   (`pstack.tmp-build` swap, with rollback if the swap fails) and
   byte-reproducible under `SOURCE_DATE_EPOCH`. Every transform anchor in the
   T8/T9/T10/T11/delegation maps is audited: an anchor that matches nothing in
   the upstream build fails the build loudly (upstream drift must be resolved
   by updating or pruning the map, never ignored).
2. **Validate** — `tools/validate.py` runs the four-stage ladder (static →
   repo YAML → gold manifest → gold load). The expected skill count is
   **derived from the package**, not hardcoded — structural changes flow
   through automatically.
3. **Doctor** — `hermes plugins doctor pstack --ci` for install-relevant
   changes (maintainer machine; needs the hermes venv).

## Repository contract

- `pstack/` is **generated content** — never hand-edit; change the converter
  and rebuild. Provenance (`.build-provenance.txt`) must record the pinned
  upstream SHA at all times.
- **Banned constructs** are defined once in `tools/bans.py` and enforced by
  both `tools/validate.py` and the CI scanner gate (`tools/scanner_gate.py`,
  which scans every UTF-8-decodable file, mirroring the real hermes install
  scanner): `tailscale.com/install.sh`, `FOR_AGENTS.md`,
  `http://127.0.0.1:4173` (package-wide), plus `subagent_type` /
  `generalPurpose` on the hermes-facing surface. Inline legacy model slugs in
  skill prose (e.g. the `PSTACK_FAST_LANE` default) are intentional fallback
  documentation, not banned.
- Encoding: LF-only, no BOM (`.gitattributes` enforces; validate.py fails on
  drift).
- Attribution: upstream MIT (© Lauren Tan) is preserved everywhere; new port
  work is © the pstack-hermes-port contributors.
- Fork patches live in `patches/` with documentation in
  [docs/PATCHES.md](docs/PATCHES.md); the drafted upstream PR text is
  [docs/UPSTREAM-PR.md](docs/UPSTREAM-PR.md).

## Pull requests

The [PR template](.github/PULL_REQUEST_TEMPLATE.md) requires: convert clean, validate
exit 0, doctor exit 0 (install-relevant), banned-construct scan, provenance
consistency. CI runs all of it plus the pinned-SHA re-check, unit tests, lint,
and a weekly upstream-drift check
([upstream-drift-watch](.github/workflows/upstream-drift-watch.yml)) that opens
a tracking issue when upstream `pstack/` changes past the pin; PRs are
auto-labeled by path (labels are created once via the `labels-bootstrap`
workflow after the repo goes public).

## Issue reports

Use the templates — platform (hermes portable / hermes slash / Cursor
dual-load) and affected skill are required fields; `hermes plugins doctor
pstack --ci` output is the most useful evidence you can attach.
