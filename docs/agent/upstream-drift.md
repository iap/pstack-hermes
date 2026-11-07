# Standalone maintenance (formerly upstream drift)

> [!IMPORTANT]
> Retired in the standalone refactor (#156). This repository is no longer
> a generated port of `cursor/plugins`: there is no upstream pin, no
> converter (`tools/convert.py` deleted), and no re-pin procedure. The
> final upstream SHA `c47b1284` is recorded as historical context in
> `CHANGELOG.md` and [standalone-decisions.md](../standalone-decisions.md).
> This file is kept as a pointer until the #159 instruction audit removes
> the remaining links to it.

Package maintenance is now direct: edit `plugin.json`, `skills/`,
`config/`, `assets/`, `README.md`, `LICENSE` and validate with
`tools/validate.py`. Model-slug drift is a separate weekly job
(`model-drift-watch` / `tools/slug_drift.py`); it updates
`tools/assets/model-panel.json` and `config/models.json` directly.

## Do not

- **Do not reintroduce a converter, pin, or rebuild step.** If upstream
  code is ever ported again, it lands as a deliberate, reviewed change to
  the hand-written package, not a regenerated tree.
- **Do not delete attribution.** `NOTICE.md` (MIT © Lauren Tan) stays.

## Rollback

To revert a landed package change, revert its PR. There is no rebuild
from a pin to re-run: the package surfaces on `master` are the source,
so a revert restores the prior hand-written tree exactly.
