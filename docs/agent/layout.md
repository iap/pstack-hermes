# Package layout

Which paths are **hand-written** (source) since the standalone refactor
(#156). The upstream converter and its generated-output rule are retired;
git history preserves the final converted state.

| Path | Kind | Notes |
|---|---|---|
| `plugin.json` | hand-written | Root agent-plugin manifest (JSON). Edit directly. |
| `skills/` | hand-written | All `SKILL.md` and references. Edit directly. |
| `config/models.json` | hand-written | Model panel; edit directly. |
| `assets/` | hand-written | Manifest asset refs. Edit directly. |
| `README.md` | hand-written | Edit directly. |
| `LICENSE` | hand-written | MIT with upstream attribution (© Lauren Tan). Edit directly. |
| `tools/`, `tools/assets/` | hand-written | Validator, bans, scanner, assets source. |
| `scripts/`, `package.json`, `bun.lock` | hand-written | Runtime tooling (`@iap/poteto`); run from the root. |
| `docs/`, `AGENTS.md`, `CONTRIBUTING.md`, `SECURITY.md`, `CHANGELOG.md` | hand-written | Docs and contract. |
| `NOTICE.md` | hand-written | Attribution / third-party notices. |

Rule: edit the package surfaces directly, then validate with
`tools/validate.py`. Never reintroduce a rebuild step (`tools/convert.py`
was deleted in #156).
