"""Hermes adaptation regressions that must not survive generated output."""

import json

import pytest
import validate


def _skill(pkg, rel, text):
    path = pkg / "skills" / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.mark.parametrize(('text', 'blocked'), [
    ('The tells are `!`, `arr[0] as T`, and a throw.', True),
    ('Run !`printf hello` on view.', True),
    ('```ts\nreturn sessions.at(0)!;\n```', False),
    ('The non-null operator is `!`.\nUse a total type.', False),
])
def test_skill_view_cannot_expand_inline_shell(tmp_path, text, blocked):
    _skill(tmp_path, 'typescript-best-practices/references/patterns.md', text)
    rep = validate.Report()
    validate.check_hermes_adaptation_contract(tmp_path, rep)
    assert bool(rep.failed) is blocked
    if blocked:
        assert 'inline-shell expansion' in '\n'.join(rep.failed)


def test_adaptation_checks_exclude_installed_dependencies(tmp_path):
    _skill(tmp_path, 'poteto-mode/scripts/node_modules/dependency/README.md', '!`printf hello`')
    rep = validate.Report()
    validate.check_hermes_adaptation_contract(tmp_path, rep)
    assert not rep.failed


def test_adaptation_contract_catches_inert_personas_and_stale_runtime_claims(tmp_path):
    pkg = tmp_path / "pkg"
    _skill(
        pkg,
        "poteto-mode/SKILL.md",
        "Use `delegate_task` (role: `leaf`, persona: poteto-agent).\n"
        "Defaults: read-only delegates lose MCP access.\n",
    )
    _skill(pkg, "no-comments/SKILL.md", "delegate_task persona: Comment Sicko\n")

    rep = validate.Report()
    validate.check_hermes_adaptation_contract(pkg, rep)

    joined = "\n".join(rep.failed)
    assert "persona:" in joined
    assert "read-only delegates lose MCP access" in joined


def test_adaptation_contract_catches_cursor_tool_names_auto_and_transcript_paths(tmp_path):
    pkg = tmp_path / "pkg"
    _skill(pkg, "interrogate/SKILL.md", "If configured value is `inherit-parent` or `auto`.\n")
    _skill(pkg, "interrogate/references/rubric.md", "Use the tools available to you (Read, Grep, Glob).\n")
    _skill(pkg, "reflect/references/judgment-reviewer.md", "Read the active transcript at <ABSOLUTE_PATH>.\n")
    _skill(pkg, "swarm/SKILL.md", "Fan out N parallel cloud workers. Not the cloud concurrency limit.\n")

    rep = validate.Report()
    validate.check_hermes_adaptation_contract(pkg, rep)

    joined = "\n".join(rep.failed)
    assert "`auto`" in joined
    assert "Read, Grep, Glob" in joined
    assert "<ABSOLUTE_PATH>" in joined
    assert "cloud workers" in joined


def test_model_panel_role_shapes_are_validated(tmp_path):
    payload = {
        "roles": {
            "reflect judgment, divergent, synthesizer": ["z-ai/glm-5.2"],
            "swarm workers": ["meituan/longcat-2.0"],
        }
    }
    asset = tmp_path / "panel.json"
    asset.write_text(json.dumps(payload), encoding="utf-8")
    pkg = tmp_path / "pkg"
    (pkg / "config").mkdir(parents=True)
    (pkg / "config" / "models.json").write_text(json.dumps(payload), encoding="utf-8")

    rep = validate.Report()
    validate.check_model_panel(pkg, rep, asset=asset)

    joined = "\n".join(rep.failed)
    assert "reflect judgment, divergent, synthesizer" in joined
    assert "swarm workers" in joined
