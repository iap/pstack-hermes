# Pipeline Hardening (anchor audit, tests, gate consolidation) — Implementation Plan

> **For agentic workers:** Executed inline in this session. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the review's P1/P2/P3 gaps: fail-loud transform anchors, a unit-test + lint safety net, one shared banned-construct source of truth, and CI/token hardening — with the shipped package byte-identical to the current build.

**Architecture:** The converter gains per-anchor hit accounting that raises `ConvertError` when any expected anchor no longer matches upstream (the "silent no-op" fix). Banned constructs move to a new `tools/bans.py` consumed by both `tools/validate.py` and a new `tools/scanner_gate.py` (replacing the inline CI heredoc, and widening the scan from `.md/.json/.txt` to every UTF-8-decodable file — verified safe against the current package). CI gains `permissions: contents: read`, a single `UPSTREAM_PIN` env var, `persist-credentials: false`, and a lint-and-tests job. A weekly drift-watch workflow tracks upstream movement past the pin.

**Tech Stack:** Python 3.11 (uv-managed, `.venv`), pytest, ruff, GitHub Actions.

## Global Constraints

- `pstack/` is generated: after all code changes the converter must reproduce the package **byte-identically excluding `.build-provenance.txt`** (tree-hash `9c860ec56047c3089182f1684a48cbb23ad85619ce9ecc37031d934ae1daa8f4` at pin `799151d91b6e12ee7dbd09f708eec108d7de9b3b`).
- Provenance fix-lines may change (they are excluded from the CI freshness comparison); package content files may not.
- Upstream source: `$TEMP/pstack-verify/cursor-plugins` at the pinned SHA; scratch builds go to `$TEMP/pstack-verify/*`, never into the committed tree except the final regeneration.
- TDD: every new function gets a failing test first (RED → GREEN).
- No commits unless the user asks; work stays in the working tree.

---

### Task 1: Tooling config (pyproject)

- Modify `pyproject.toml`: dev group `["pyyaml>=6.0", "pytest>=8.3", "ruff==0.14.10"]`; `[tool.ruff]` line-length 100, target py311, exclude `pstack/` `.venv/`; lint select `["E4","E7","E9","F","I","UP","B"]` (ruff defaults + isort + pyupgrade + bugbear; E501 excluded — data-literal-heavy code); `[tool.pytest.ini_options] testpaths=["tools/tests"]`.
- Install uv (standalone installer), `uv sync` to regenerate `uv.lock` + install pytest/ruff into `.venv`.

### Task 2: Anchor accounting in convert.py (TDD)

- Test `tools/tests/test_convert_accounting.py` (RED first):
  - `apply_map(files, mapping, *, map_name, st) -> int` — applies ordered `(old,new)` pairs per file, writes back only on change, returns files-changed, records `st.anchor_hits[(map_name, index)] += occurrences`.
  - `audit_anchor_hits(maps: dict[str, list[tuple[str, str]]], st) -> None` — raises `ConvertError` naming every zero-hit anchor; passes when all hit.
- Implementation: `Stats.anchor_hits: dict[tuple[str, int], int]`; refactor the T8 / T9+T10 / T11 / DELEGATION loops to call `apply_map` (preserving replacement order exactly: within a file, pairs apply in the same sequence as today, so output is byte-identical). Audit runs at the end of `apply_phase1_transforms` over T8_MAP, T9_MAP, T10_MAP, T11_MAP, DELEGATION_MAP.
- Dead anchors found by the audit at the current pin: remove from the maps (they never fire; git history keeps them). Conditional-by-design passes (T5 localhost neutralization, the source-playbook note) stay outside the audit.
- Provenance gains one line: `anchor audit: N/N anchors applied (0 dead)`.

### Task 3: tools/bans.py + tools/scanner_gate.py (TDD)

- Test `tools/tests/test_bans.py` (RED first): security bans hit any decodable extension (`.ts` included); vocab bans skip `agents/`, `.cursor-plugin/`, `.build-provenance.txt`; clean tree → `[]`; undecodable binary content is skipped.
- `tools/bans.py` API: `SECURITY_BANS: tuple[tuple[str, str], ...]` (needle, reason), `DELEGATION_VOCAB_BANS: tuple[str, ...]`, `VOCAB_EXEMPT_PREFIXES: tuple[str, ...]`, `iter_text_files(pkg) -> Iterator[tuple[Path, str]]` (UTF-8-decodable files, rel-path + text), `find_violations(pkg) -> list[str]`.
- `tools/scanner_gate.py`: `run(pkg: Path) -> int` + argparse `--package`; exit 0 clean / 1 violations / 2 bad path. Test: clean tmp tree → 0; planted violation → 1 with the needle in output.
- Gate the baseline build: `scanner_gate.py --package $TEMP/pstack-verify/baseline-pstack` must exit 0.

### Task 4: validate.py updates

- Fix module docstring exit codes (0 all-pass; 1 static fail; 2 = gold RAN and failed; gold unavailable → skip, exit 0/1 by static result).
- Import shared constants from convert (`SCHEMA_URL`, `MANIFEST_NAME_RE`, `SKILL_NAME_RE`, `TEXT_EXTS`) — local duplicates removed; keep `LOADER_WHITELIST` (10-field, tolerates `extensions`) distinct from convert's 9-field emitted whitelist, with comments.
- F-publish check consumes `bans.find_violations(pkg)` (strictly stronger: adds the loopback ban + scoped vocab bans to the all-files scan).
- New `check_model_panel(pkg, rep, asset=SCRIPT_DIR/"assets/model-panel.json")` (TDD via `tools/tests/test_validate_panel.py`): parse both, fail on drift/missing/malformed, ok on equal (compares parsed `roles`, not bytes).

### Task 5: convert.py robustness + doc accuracy

- Atomic swap rollback: if `out.rename(final_out)` fails, restore `prev` before re-raising (no window with the package absent).
- Docstring fixes: "exactly two frontmatter names" → "the SKILL.md frontmatter name fixes" (module docstring + step comment); "strict 10-field whitelist" comment → 9-field emitted.
- Drop `import json as _json` (module-level `json` already imported); drop dead `".gitignore"` from `TEXT_EXTS` (dotfiles match the `path.name` check in `is_text_candidate`, suffix is `""`).

### Task 6: ci.yml hardening

- Workflow-level `permissions: contents: read`; `env: UPSTREAM_PIN: 799151d…` replacing all four literals; `persist-credentials: false` on both checkouts.
- Scanner-gate step → `uv run --frozen tools/scanner_gate.py --package "$GITHUB_WORKSPACE/pstack"`.
- New `lint-and-tests` job (ubuntu): checkout (persist-credentials: false) → setup-uv → `uv run --frozen ruff check tools` → `uv run --frozen pytest -q`.

### Task 7: upstream-drift-watch.yml

- Weekly cron + `workflow_dispatch`; `permissions: contents: read, issues: write`; no third-party actions. `git ls-remote` upstream HEAD; if ≠ pin and `git diff --quiet pin head -- pstack` (blobless clone) shows real pstack changes → create/comment a tracking issue via `gh` (search by title marker, idempotent).

### Task 8: docs + final verification

- CONTRIBUTING.md: banned constructs now defined by `tools/bans.py` (drop the inaccurate "Cursor model slugs" claim, note inline model defaults are intentional); add tests/lint to the dev loop and PR checklist.
- README.md: verification ladder mentions unit tests + lint + scanner gate; Development section gains `uv run --frozen pytest`.
- Regenerate committed `pstack/` with the new converter; tree-hash must equal `9c860ec5…` (excl. provenance).
- Full pass: `uv run --frozen tools/validate.py` (exit 0), `pytest -q`, `ruff check tools`, `scanner_gate.py` on the package, YAML parse of all workflows.
