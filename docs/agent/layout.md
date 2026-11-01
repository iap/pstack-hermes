# Package layout

Which paths are **generated** (converter output) vs **hand-written** (source):

| Path | Kind | Notes |
|---|---|---|
| `plugin.json` | generated | Root agent-plugin manifest (JSON). Rebuilt by `tools/convert.py`. Never hand-edit. |
| `skills/` | generated | All `SKILL.md` and references. Rebuilt by converter. |
| `config/models.json` | generated | Model panel from `tools/assets/model-panel.json`. |
| `assets/` | copied | Verbatim from upstream Cursor manifest asset refs. |
| `.build-provenance.txt` | generated | Rebuild stamp. |
| `tools/`, `tools/assets/` | hand-written | Converter, validator, bans, assets source. Edit here, then rebuild. |
| `docs/`, `AGENTS.md`, `CONTRIBUTING.md`, `README.md` | hand-written | Docs and contract. |
| `agents/`, `.cursor-plugin/` | source (dual-load) | Cursor dual-load artifacts; inert on hermes portable path. |

Rule: change `tools/` / `tools/assets/`, rebuild with `tools/convert.py`, validate. Never hand-edit generated surfaces.
