# Contributing

Thanks for helping port and maintain pstack on hermes. The repo is small and
the contract is strict — read this once and the CI will never surprise you.

## Setup

```sh
uv sync                                   # pinned CPython 3.11 + pyyaml (dev group)
uv run --frozen tools/validate.py         # must exit 0 before you start
```

Python is pinned via `.python-version` and `uv.lock`; never commit interpreter
or dependency drift.

## The pipeline

1. **Convert** — `tools/convert.py` rebuilds `pstack/` from any pstack clone
   (or a fresh upstream clone at the pinned SHA). Builds are atomic
   (`pstack.tmp-build` swap) and byte-reproducible under `SOURCE_DATE_EPOCH`.
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
- **Banned constructs** (scanner-clean invariants, CI-enforced):
  `subagent_type`, `generalPurpose`, Cursor model slugs,
  `tailscale.com/install.sh`, `http://127.0.0.1:4173`.
- Encoding: LF-only, no BOM (`.gitattributes` enforces; validate.py fails on
  drift).
- Attribution: upstream MIT (© Lauren Tan) is preserved everywhere; new port
  work is © the pstack-hermes-port contributors.
- Fork patches live in `patches/` with documentation in
  [docs/PATCHES.md](docs/PATCHES.md); the drafted upstream PR text is
  [docs/UPSTREAM-PR.md](docs/UPSTREAM-PR.md).

## Pull requests

The [PR template](.github/pull_request_template.md) requires: convert clean, validate
exit 0, doctor exit 0 (install-relevant), banned-construct scan, provenance
consistency. CI runs all of it plus the pinned-SHA re-check on every push and
PR; PRs are auto-labeled by path (labels are created once via the
`labels-bootstrap` workflow after the repo goes public).

## Issue reports

Use the templates — platform (hermes portable / hermes slash / Cursor
dual-load) and affected skill are required fields; `hermes plugins doctor
pstack --ci` output is the most useful evidence you can attach.
