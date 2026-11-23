"""Skills must default subagents to the parent chat model, not a concrete slug.

Regression for #239: the shipped panel is a documentation artifact that no
skill reads at runtime. With no per-profile pstack-models.json or role line,
a concrete embedded slug is the only model the skill will instruct the agent
to use. Those slugs are Cursor-family names Hermes rejects, so the fallback
must be to omit `model` and let the subagent inherit the parent chat model.
"""

import re
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[2] / "skills"

# A concrete model assigned as a default/fallback by a skill instruction.
# The setup-pstack effort-ladder example ("turns `...` into `...`") is not a
# default and deliberately does not match.
CONCRETE_DEFAULT_RE = re.compile(
    r"(?:default(?:s| to)?|fallback|use|choose from|one each on|"
    r"go to your strongest judgment model|read the `judgment and prose`)\s*"
    r"(?:one each on\s*)?"
    r"`(?:grok|claude|gpt|meituan|qwen|meta|z-ai)[^`]*`",
    re.IGNORECASE,
)

# Skills that spawn subagents and name a panel role line explicitly. The
# fallback changes to parent model; explicit per-profile overrides do not.
ROLE_LINE_SKILLS = {
    "how/SKILL.md": ["how explorer", "how explainer"],
    "why/SKILL.md": ["why investigators", "why synthesizer"],
    "swarm/SKILL.md": ["swarm workers"],
    "arena/SKILL.md": ["arena runners", "arena cross-judge pool"],
    "interrogate/SKILL.md": ["interrogate reviewers"],
    "architect/SKILL.md": ["architect runners"],
    "reflect/SKILL.md": ["reflect judgment, divergent, synthesizer", "reflect tooling"],
    "poteto-mode/SKILL.md": ["feature, refactoring", "judgment and prose", "hardest tasks"],
}

# Playbooks defer to poteto-mode's role mapping; they name the configured
# model, not the literal role label.
PLAYBOOKS = [
    "poteto-mode/playbooks/feature.md",
    "poteto-mode/playbooks/bug-fix.md",
    "poteto-mode/playbooks/perf-issue.md",
    "poteto-mode/playbooks/refactoring.md",
    "poteto-mode/playbooks/hillclimb.md",
    "poteto-mode/playbooks/multi-phase-plan.md",
]


def test_no_concrete_model_defaults_in_skills():
    offenders = []
    for md in sorted(SKILLS.rglob("*.md")):
        for lineno, line in enumerate(md.read_text(encoding="utf-8").splitlines(), 1):
            if CONCRETE_DEFAULT_RE.search(line):
                offenders.append(f"{md.relative_to(SKILLS)}:{lineno}: {line.strip()}")
    assert not offenders, "concrete model defaults in skill markdown:\n" + "\n".join(offenders)


def test_parent_model_fallback_is_documented():
    for rel in list(ROLE_LINE_SKILLS) + PLAYBOOKS:
        text = (SKILLS / rel).read_text(encoding="utf-8").lower()
        assert "parent chat model" in text or "parent model" in text, rel


def test_explicit_panel_role_overrides_remain():
    for rel, role_lines in ROLE_LINE_SKILLS.items():
        text = (SKILLS / rel).read_text(encoding="utf-8")
        for role in role_lines:
            assert f"`{role}`" in text, (rel, role)
