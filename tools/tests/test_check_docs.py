"""check_docs must catch the drift classes the root-layout migration produced.

Each test pins one failure mode: a broken router link, a generated path
mislabelled as hand-written (README.md), a stale `pstack/` subdirectory path,
a pin-declarer list that disagrees with check_pins, and a publish `cp` source
that no longer exists (after-install.md). The final test runs the gate against
this repository so the checked-in docs cannot drift again.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_docs  # noqa: E402


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _router_tree(tmp_path: Path, agents: str) -> Path:
    _write(tmp_path / "AGENTS.md", agents)
    _write(tmp_path / "docs" / "agent" / "README.md", "# router\n")
    return tmp_path


def test_router_links_resolve(tmp_path):
    root = _router_tree(tmp_path, "[layout](docs/agent/layout.md)\n[ext](https://example.com)\n")
    _write(tmp_path / "docs" / "agent" / "layout.md", "# layout\n")
    assert check_docs.check_router_links(root) == []


def test_broken_router_link_fails(tmp_path):
    root = _router_tree(tmp_path, "[gone](docs/agent/nope.md)\n")
    problems = check_docs.check_router_links(root)
    assert any("broken link target docs/agent/nope.md" in item for item in problems)


def test_readme_marked_hand_written_fails(tmp_path):
    _write(tmp_path / ".gitattributes", "README.md linguist-generated=true\n")
    _write(
        tmp_path / "docs" / "agent" / "layout.md",
        "| Path | Kind | Notes |\n|---|---|---|\n| `README.md` | hand-written | docs |\n",
    )
    problems = check_docs.check_layout_manifest(tmp_path)
    assert any("README.md" in item and "hand-written" in item for item in problems)


def test_generated_path_not_in_gitattributes_fails(tmp_path):
    _write(tmp_path / ".gitattributes", "README.md linguist-generated=true\n")
    _write(
        tmp_path / "docs" / "agent" / "layout.md",
        "| Path | Kind | Notes |\n|---|---|---|\n| `docs/` | generated | nope |\n",
    )
    problems = check_docs.check_layout_manifest(tmp_path)
    assert any("docs/" in item and "does not mark it generated" in item for item in problems)


def test_layout_manifest_matches(tmp_path):
    _write(
        tmp_path / ".gitattributes",
        "README.md linguist-generated=true\nskills/** linguist-generated=true\n",
    )
    _write(
        tmp_path / "docs" / "agent" / "layout.md",
        "| Path | Kind | Notes |\n|---|---|---|\n"
        "| `README.md` | generated | built |\n"
        "| `skills/` | generated | built |\n"
        "| `tools/` | hand-written | source |\n",
    )
    assert check_docs.check_layout_manifest(tmp_path) == []


def test_stale_subdirectory_path_fails(tmp_path):
    _write(tmp_path / "AGENTS.md", "cd pstack/skills/poteto-mode/scripts\n")
    problems = check_docs.check_stale_paths(tmp_path)
    assert any("pstack/skills" in item for item in problems)


def test_stale_path_in_readme_fails(tmp_path):
    _write(tmp_path / "README.md", "git show origin/main:pstack/skills/x\n")
    problems = check_docs.check_stale_paths(tmp_path)
    assert any("README.md" in item and "pstack/skills" in item for item in problems)


def test_stale_subdirectory_install_route_in_readme_fails(tmp_path):
    _write(
        tmp_path / "README.md",
        "Hermes updates unpinned `dist` root installs and `master` subdirectory\n"
        "installs.\n",
    )
    problems = check_docs.check_stale_install_route(tmp_path)
    assert any("subdirectory-install route" in item for item in problems)


def test_stale_subdirectory_install_route_in_using_fails(tmp_path):
    _write(
        tmp_path / "docs" / "USING.md",
        "Subdirectory updates replace shipped skills; in-place edits are not durable.\n",
    )
    problems = check_docs.check_stale_install_route(tmp_path)
    assert any("docs/USING.md" in item for item in problems)


def test_legacy_subdirectory_install_command_fails(tmp_path):
    _write(
        tmp_path / "README.md",
        "hermes plugins install iap/pstack-hermes/pstack --enable\n",
    )
    problems = check_docs.check_stale_install_route(tmp_path)
    assert any("subdirectory-install route" in item for item in problems)


def test_legacy_subdirectory_install_command_with_trailing_slash_fails(tmp_path):
    _write(
        tmp_path / "README.md",
        "hermes plugins install iap/pstack-hermes/pstack/ --enable\n",
    )
    problems = check_docs.check_stale_install_route(tmp_path)
    assert any("subdirectory-install route" in item for item in problems)


def test_legacy_git_url_install_command_fails(tmp_path):
    _write(
        tmp_path / "README.md",
        "hermes plugins install https://github.com/iap/pstack-hermes.git/pstack --enable\n",
    )
    problems = check_docs.check_stale_install_route(tmp_path)
    assert any("subdirectory-install route" in item for item in problems)


def test_legacy_ssh_url_install_command_fails(tmp_path):
    _write(
        tmp_path / "README.md",
        "hermes plugins install git@github.com:iap/pstack-hermes/pstack --enable\n",
    )
    problems = check_docs.check_stale_install_route(tmp_path)
    assert any("subdirectory-install route" in item for item in problems)


def test_legacy_userless_scp_install_command_fails(tmp_path):
    _write(
        tmp_path / "README.md",
        "hermes plugins install github.com:iap/pstack-hermes/pstack --enable\n",
    )
    problems = check_docs.check_stale_install_route(tmp_path)
    assert any("subdirectory-install route" in item for item in problems)


def test_unrelated_scp_install_command_is_not_flagged(tmp_path):
    _write(
        tmp_path / "README.md",
        "hermes plugins install example.com:iap/pstack-hermes/pstack --enable\n",
    )
    assert check_docs.check_stale_install_route(tmp_path) == []


def test_legacy_markdown_link_text_fails(tmp_path):
    _write(
        tmp_path / "README.md",
        "[https://github.com/iap/pstack-hermes/pstack](https://example.com)\n",
    )
    problems = check_docs.check_stale_install_route(tmp_path)
    assert any("subdirectory-install route" in item for item in problems)


def test_legacy_markdown_emphasis_fails(tmp_path):
    _write(
        tmp_path / "README.md",
        "See *https://github.com/iap/pstack-hermes/tree/master/pstack*.\n",
    )
    problems = check_docs.check_stale_install_route(tmp_path)
    assert any("subdirectory-install route" in item for item in problems)


def test_legacy_hash_subdir_install_command_fails(tmp_path):
    _write(
        tmp_path / "README.md",
        "hermes plugins install iap/pstack-hermes#pstack --enable\n",
    )
    problems = check_docs.check_stale_install_route(tmp_path)
    assert any("subdirectory-install route" in item for item in problems)


def test_legacy_install_option_before_identifier_fails(tmp_path):
    _write(
        tmp_path / "README.md",
        "hermes plugins install --enable iap/pstack-hermes/pstack\n",
    )
    problems = check_docs.check_stale_install_route(tmp_path)
    assert any("subdirectory-install route" in item for item in problems)


def test_legacy_install_option_with_value_before_identifier_fails(tmp_path):
    _write(
        tmp_path / "README.md",
        "hermes plugins install --force --ref abc123 iap/pstack-hermes/pstack\n",
    )
    problems = check_docs.check_stale_install_route(tmp_path)
    assert any("subdirectory-install route" in item for item in problems)


def test_other_owner_prefix_is_not_flagged(tmp_path):
    _write(
        tmp_path / "README.md",
        "hermes plugins install acme-iap/pstack-hermes/pstack --enable\n",
    )
    assert check_docs.check_stale_install_route(tmp_path) == []


def test_nested_path_is_not_flagged(tmp_path):
    _write(
        tmp_path / "README.md",
        "hermes plugins install acme/iap/pstack-hermes/pstack --enable\n",
    )
    assert check_docs.check_stale_install_route(tmp_path) == []


def test_nested_url_path_is_not_flagged(tmp_path):
    _write(
        tmp_path / "README.md",
        "hermes plugins install https://github.com/acme/iap/pstack-hermes/pstack --enable\n",
    )
    assert check_docs.check_stale_install_route(tmp_path) == []


def test_legacy_install_other_option_before_identifier_fails(tmp_path):
    _write(
        tmp_path / "README.md",
        "hermes plugins install --allow-removed iap/pstack-hermes/pstack\n",
    )
    problems = check_docs.check_stale_install_route(tmp_path)
    assert any("subdirectory-install route" in item for item in problems)


def test_legacy_install_continuation_before_identifier_fails(tmp_path):
    _write(
        tmp_path / "README.md",
        "hermes plugins install \\\n  iap/pstack-hermes/pstack --enable\n",
    )
    problems = check_docs.check_stale_install_route(tmp_path)
    assert any("subdirectory-install route" in item for item in problems)


def test_legacy_install_quoted_ref_separated_fails(tmp_path):
    _write(
        tmp_path / "README.md",
        "hermes plugins install --ref \"$SHA\" iap/pstack-hermes/pstack\n",
    )
    problems = check_docs.check_stale_install_route(tmp_path)
    assert any("subdirectory-install route" in item for item in problems)


def test_legacy_install_quoted_ref_equals_fails(tmp_path):
    _write(
        tmp_path / "README.md",
        "hermes plugins install --ref=\"$SHA\" iap/pstack-hermes/pstack\n",
    )
    problems = check_docs.check_stale_install_route(tmp_path)
    assert any("subdirectory-install route" in item for item in problems)


def test_legacy_install_newline_inside_inline_code_fails(tmp_path):
    _write(
        tmp_path / "README.md",
        "Run `hermes plugins install\niap/pstack-hermes/pstack --enable`.\n",
    )
    problems = check_docs.check_stale_install_route(tmp_path)
    assert any("subdirectory-install route" in item for item in problems)


def test_legacy_schemeless_github_install_fails(tmp_path):
    _write(
        tmp_path / "README.md",
        "hermes plugins install github.com/iap/pstack-hermes/pstack --enable\n",
    )
    problems = check_docs.check_stale_install_route(tmp_path)
    assert any("subdirectory-install route" in item for item in problems)


def test_root_install_without_subdir_is_not_flagged(tmp_path):
    _write(
        tmp_path / "README.md",
        "hermes plugins install iap/pstack-hermes --enable\n",
    )
    assert check_docs.check_stale_install_route(tmp_path) == []


def test_legacy_tree_url_install_fails(tmp_path):
    _write(
        tmp_path / "README.md",
        "hermes plugins install https://github.com/iap/pstack-hermes/tree/master/pstack --enable\n",
    )
    problems = check_docs.check_stale_install_route(tmp_path)
    assert any("subdirectory-install route" in item for item in problems)


def test_legacy_tree_url_with_query_fails(tmp_path):
    _write(
        tmp_path / "README.md",
        "hermes plugins install https://github.com/iap/pstack-hermes/tree/master/pstack?plain=1\n",
    )
    problems = check_docs.check_stale_install_route(tmp_path)
    assert any("subdirectory-install route" in item for item in problems)


def test_legacy_tree_url_with_sentence_period_fails(tmp_path):
    _write(
        tmp_path / "README.md",
        "See https://github.com/iap/pstack-hermes/tree/master/pstack.\n",
    )
    problems = check_docs.check_stale_install_route(tmp_path)
    assert any("subdirectory-install route" in item for item in problems)


def test_dot_named_subdirectory_is_not_flagged(tmp_path):
    _write(
        tmp_path / "README.md",
        "hermes plugins install iap/pstack-hermes/pstack.tools --enable\n",
    )
    assert check_docs.check_stale_install_route(tmp_path) == []


def test_legacy_install_command_with_semicolon_fails(tmp_path):
    _write(
        tmp_path / "README.md",
        "hermes plugins install iap/pstack-hermes/pstack; echo done\n",
    )
    problems = check_docs.check_stale_install_route(tmp_path)
    assert any("subdirectory-install route" in item for item in problems)


def test_similarly_named_subdirectory_is_not_flagged(tmp_path):
    _write(
        tmp_path / "README.md",
        "hermes plugins install iap/pstack-hermes/pstack-tools --enable\n",
    )
    assert check_docs.check_stale_install_route(tmp_path) == []


def test_root_git_url_install_is_not_flagged(tmp_path):
    _write(
        tmp_path / "README.md",
        "hermes plugins install https://github.com/iap/pstack-hermes.git --enable\n",
    )
    assert check_docs.check_stale_install_route(tmp_path) == []


def test_migration_note_is_not_flagged(tmp_path):
    _write(
        tmp_path / "README.md",
        "Installs created before the root-layout migration (the old\n"
        "source-subdirectory route) cannot update in place. Remove it,\n"
        "then run `hermes plugins install iap/pstack-hermes --enable`.\n",
    )
    assert check_docs.check_stale_install_route(tmp_path) == []


def test_upstream_repo_path_is_not_flagged(tmp_path):
    _write(
        tmp_path / "docs" / "agent" / "upstream-drift.md",
        "git -C <clone> log --oneline <pin>..HEAD --\n  pstack/` (upstream path)\n",
    )
    assert check_docs.check_stale_paths(tmp_path) == []


def test_pr_template_bare_pstack_path_fails(tmp_path):
    _write(tmp_path / ".github" / "PULL_REQUEST_TEMPLATE.md", "if `pstack/` changed\n")
    problems = check_docs.check_stale_paths(tmp_path)
    assert any("PULL_REQUEST_TEMPLATE" in item for item in problems)


def test_release_packaging_missing_source_fails(tmp_path):
    _write(
        tmp_path / ".github" / "workflows" / "release.yml",
        'run: |\n  zip -r pstack-"${TAG_NAME}".zip plugin.json after-install.md\n',
    )
    problems = check_docs.check_release_sources(tmp_path)
    assert any("after-install.md" in item for item in problems)


def test_release_packaging_sources_exist(tmp_path):
    _write(tmp_path / "plugin.json", "{}\n")
    _write(tmp_path / "README.md", "# x\n")
    _write(
        tmp_path / ".github" / "workflows" / "release.yml",
        'run: |\n  zip -r pstack-"${TAG_NAME}".zip plugin.json README.md\n',
    )
    assert check_docs.check_release_sources(tmp_path) == []


def test_repository_docs_are_clean():
    code, lines = check_docs.check(Path(check_docs.ROOT))
    assert code == 0, "\n".join(lines)


def test_stale_root_generated_file_path_fails(tmp_path):
    _write(tmp_path / "AGENTS.md", "copy pstack/plugin.json into the package\n")
    problems = check_docs.check_stale_paths(tmp_path)
    assert any("pstack/plugin.json" in item for item in problems)


def test_bare_pstack_prose_is_not_flagged(tmp_path):
    _write(
        tmp_path / "docs" / "USING.md",
        "The generated package lives at the repository root (not a `pstack/`\n"
        "subdirectory).\n",
    )
    assert check_docs.check_stale_paths(tmp_path) == []


def test_release_packaging_without_zip_line_fails(tmp_path):
    _write(
        tmp_path / ".github" / "workflows" / "release.yml",
        'run: |\n  tar -czf out.tgz .\n',
    )
    problems = check_docs.check_release_sources(tmp_path)
    assert any("no zip invocation" in item for item in problems)


def test_release_packaging_allows_optional_assets(tmp_path):
    _write(tmp_path / "plugin.json", "{}\n")
    _write(
        tmp_path / ".github" / "workflows" / "release.yml",
        'run: |\n  zip -r pstack-"${TAG_NAME}".zip plugin.json assets/\n',
    )
    assert check_docs.check_release_sources(tmp_path) == []


def test_bare_package_path_in_agent_contract_fails(tmp_path):
    _write(tmp_path / "AGENTS.md", "The package lives at pstack/ in this repo.\n")
    problems = check_docs.check_stale_paths(tmp_path)
    assert any("bare pstack/" in item for item in problems)


def test_generated_marker_missing_from_layout_fails(tmp_path):
    _write(tmp_path / ".gitattributes", "LICENSE linguist-generated=true\n")
    _write(
        tmp_path / "docs" / "agent" / "layout.md",
        "| Path | Kind | Notes |\n|---|---|---|\n| `README.md` | generated | x |\n",
    )
    problems = check_docs.check_layout_manifest(tmp_path)
    assert any("LICENSE" in item and "does not list it" in item for item in problems)


def test_generated_marker_listed_in_layout_passes(tmp_path):
    _write(tmp_path / ".gitattributes", "LICENSE linguist-generated=true\n")
    _write(
        tmp_path / "docs" / "agent" / "layout.md",
        "| Path | Kind | Notes |\n|---|---|---|\n| `LICENSE` | generated | x |\n",
    )
    assert check_docs.check_layout_manifest(tmp_path) == []


def _model_tree(tmp_path, panel_roles, table_rows):
    import json

    panel = tmp_path / "tools" / "assets" / "model-panel.json"
    panel.parent.mkdir(parents=True)
    panel.write_text(json.dumps({"roles": panel_roles}), encoding="utf-8")
    body = "## The shipped panel\n\n| Role | Default |\n|---|---|\n" + table_rows + "\n\n## Next\n"
    _write(tmp_path / "docs" / "MODELS.md", body)
    return tmp_path


def test_model_map_accepts_a_matching_table(tmp_path):
    root = _model_tree(
        tmp_path,
        {"reflect tooling": "qwen/qwen3-30b-a3b-instruct-2507"},
        "| reflect tooling | `qwen/qwen3-30b-a3b-instruct-2507` |\n",
    )

    assert check_docs.check_model_map(root) == []


def test_model_map_flags_a_stale_slug(tmp_path):
    root = _model_tree(
        tmp_path,
        {"reflect tooling": "qwen/qwen3-30b-a3b-instruct-2507"},
        "| reflect tooling | `qwen/qwen-2.5-7b-instruct` |\n",
    )

    problems = check_docs.check_model_map(root)

    assert any("reflect tooling" in p and "panel has" in p for p in problems)


def test_model_map_flags_a_missing_role(tmp_path):
    root = _model_tree(
        tmp_path,
        {"reflect tooling": "qwen/qwen3-30b-a3b-instruct-2507"},
        "",
    )

    assert any("missing from shipped panel" in p for p in check_docs.check_model_map(root))


def test_model_map_flags_a_role_the_panel_no_longer_defines(tmp_path):
    root = _model_tree(
        tmp_path,
        {"reflect tooling": "qwen/qwen3-30b-a3b-instruct-2507"},
        "| reflect tooling | `qwen/qwen3-30b-a3b-instruct-2507` |\n| ghost role | `x/y-1.0` |\n",
    )

    assert any("does not define" in p for p in check_docs.check_model_map(root))


def test_model_map_flags_duplicate_rows_that_could_hide_a_stale_slug(tmp_path):
    rows = (
        "| reflect tooling | `qwen/qwen-2.5-7b-instruct` |\n"
        "| reflect tooling | `qwen/qwen3-30b-a3b-instruct-2507` |\n"
    )
    root = _model_tree(
        tmp_path,
        {"reflect tooling": "qwen/qwen3-30b-a3b-instruct-2507"},
        rows,
    )

    problems = check_docs.check_model_map(root)

    assert any("duplicate row" in p for p in problems)


VOCAB_MAP_BLOCK = """<!-- VOCAB-MAP-BEGIN -->
```json
{
  "version": 1,
  "gates": {
    "tools/bans.py:DELEGATION_VOCAB_BANS": ["`Task`", "subagent_type"],
    "tools/bans.py:TRANSCRIPT_VOCAB_BANS": ["agent-transcripts"],
    "tools/validate.py:HERMES_ADAPTATION_BANS": ["persona:"],
    "tools/validate.py:check_phase1:t9_toks": ["create-skill"]
  }
}
```
<!-- VOCAB-MAP-END -->
"""

VOCAB_DOC = """# Hermes vocabulary

## Canonical mapping

| Use this (hermes) | Banned alias (Cursor) |
|---|---|
| `delegate_task` | `` `Task` `` / `subagent_type` |
| `clarify` | `AskQuestion` |

## Enforcement

""" + VOCAB_MAP_BLOCK

VOCAB_SKILL = """| Use this (hermes) | Banned alias (Cursor, described) |
|---|---|
| `delegate_task` | described task type |
| `clarify` | described question harness |
"""

VOCAB_BANS = '''DELEGATION_VOCAB_BANS: tuple[str, ...] = ("`Task`", "subagent_type")
TRANSCRIPT_VOCAB_BANS: tuple[str, ...] = ("agent-transcripts",)
'''

VOCAB_VALIDATE = '''HERMES_ADAPTATION_BANS = {"persona:": "why"}

def check_phase1():
    t9_toks = {"create-skill": "why"}
'''


def _vocab_tree(tmp_path, doc=VOCAB_DOC, skill=VOCAB_SKILL, bans=VOCAB_BANS, validate=VOCAB_VALIDATE):
    _write(tmp_path / "docs" / "hermes-vocabulary.md", doc)
    _write(tmp_path / "skills" / "hermes-vocabulary" / "SKILL.md", skill)
    _write(tmp_path / "tools" / "bans.py", bans)
    _write(tmp_path / "tools" / "validate.py", validate)
    return tmp_path


def test_vocab_map_accepts_matching_gate_lists(tmp_path):
    assert check_docs.check_vocab_map(_vocab_tree(tmp_path)) == []


def test_vocab_map_flags_a_desynced_gate_list(tmp_path):
    bans = VOCAB_BANS.replace('"subagent_type"', '"subagent_type", "AskQuestion"')
    root = _vocab_tree(tmp_path, bans=bans)

    problems = check_docs.check_vocab_map(root)

    assert any("docs/hermes-vocabulary.md" in p and "AskQuestion" in p for p in problems)
    assert check_docs.check(root)[0] == 1


def test_vocab_map_flags_a_gate_token_missing_from_the_code(tmp_path):
    bans = VOCAB_BANS.replace('"`Task`"', '"other"')
    root = _vocab_tree(tmp_path, bans=bans)

    problems = check_docs.check_vocab_map(root)

    assert any("tools/bans.py" in p and "`Task`" in p for p in problems)


def test_vocab_map_flags_a_drifted_skill_row(tmp_path):
    skill = VOCAB_SKILL.replace("| `clarify` |", "| `ask` |")
    root = _vocab_tree(tmp_path, skill=skill)

    problems = check_docs.check_vocab_map(root)

    assert any("skills/hermes-vocabulary/SKILL.md" in p for p in problems)


def test_vocab_map_flags_an_unenforced_canonical_alias(tmp_path):
    validate = VOCAB_VALIDATE.replace('"create-skill": "why"', '"other": "why"')
    root = _vocab_tree(tmp_path, validate=validate)

    problems = check_docs.check_vocab_map(root)

    assert any("tools/validate.py" in p and "create-skill" in p for p in problems)


def test_vocab_map_requires_a_gate_constant_in_its_declared_file(tmp_path):
    bans = "\n".join(
        line for line in VOCAB_BANS.splitlines() if "DELEGATION_VOCAB_BANS" not in line
    ) + "\n"
    validate = VOCAB_VALIDATE + '\nDELEGATION_VOCAB_BANS: tuple[str, ...] = ("`Task`", "subagent_type")\n'
    root = _vocab_tree(tmp_path, bans=bans, validate=validate)

    problems = check_docs.check_vocab_map(root)

    assert any("tools/bans.py" in p and "DELEGATION_VOCAB_BANS" in p for p in problems)


def test_vocab_map_flags_a_gate_key_without_checker_coverage(tmp_path):
    doc = VOCAB_DOC.replace(
        '"tools/bans.py:TRANSCRIPT_VOCAB_BANS": ["agent-transcripts"],',
        '"tools/bans.py:TRANSCRIPT_VOCAB_BANS": ["agent-transcripts"],\n'
        '    "tools/validate.py:NEW_VOCAB_BANS": ["new-alias"],',
    )
    root = _vocab_tree(tmp_path, doc=doc)

    problems = check_docs.check_vocab_map(root)

    assert any("NEW_VOCAB_BANS" in p for p in problems)


def test_repository_vocabulary_map_is_clean():
    assert check_docs.check_vocab_map(Path(check_docs.ROOT)) == []
