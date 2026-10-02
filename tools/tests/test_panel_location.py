"""setup-pstack must not write the model panel into the plugin directory.

`hermes plugins update` (and any reinstall) replaces the installed package tree,
so a panel written inside it is silently discarded - the user's model choices
revert to the shipped defaults with no warning. The write target therefore lives
in the hermes config directory, beside `config.yaml`, which survives updates.

The assertions run against the **generated** `setup-pstack/SKILL.md`, not just the
converter source. Asserting on the source alone is only sufficient while every
shipped instruction is produced by a map entry; if a future map or template ever
hardcodes the old path, source-level assertions would not see it. (Verified: a
counterfactual that reintroduced the in-package wording passed the source-only
version of these tests.)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import convert as cv  # noqa: E402

REPO = Path(cv.__file__).resolve().parents[1]
UPSTREAM = Path(
    r"C:\Users\iap\.openclaw-autoclaw\workspace\.cluster\pstack-hermes"
    r"\repos\cursor-plugins\pstack"
)

# "in this plugin's directory" / "next to plugin.json" - the pre-fix wording.
IN_PACKAGE_WRITE = "in this plugin" + chr(39) + "s directory"
NEXT_TO_MANIFEST = "next to plugin.json"


def _built_skills() -> dict[str, str]:
    """Convert once from the pinned upstream and return {skill: text}."""
    import subprocess
    import tempfile

    out = Path(tempfile.mkdtemp()) / "pkg"
    proc = subprocess.run(
        [
            sys.executable,
            str(REPO / "tools" / "convert.py"),
            "--source", str(UPSTREAM),
            "--out", str(out),
        ],
        cwd=REPO, capture_output=True, text=True,
    )
    assert proc.returncode == 0, (proc.stdout + proc.stderr)[-600:]
    return {
        p.parent.name: p.read_text(encoding="utf-8")
        for p in (out / "skills").glob("*/SKILL.md")
    }


def test_no_shipped_skill_tells_the_agent_to_write_into_the_package():
    skills = _built_skills()
    offenders = {
        name: [ln for ln in text.splitlines() if IN_PACKAGE_WRITE in ln or NEXT_TO_MANIFEST in ln]
        for name, text in skills.items()
        if IN_PACKAGE_WRITE in text or NEXT_TO_MANIFEST in text
    }
    assert not offenders, f"shipped skills still write into the plugin dir: {offenders}"


def test_setup_pstack_writes_beside_config_yaml():
    text = _built_skills()["setup-pstack"]
    assert "pstack-models.json" in text
    assert "config.yaml" in text


def test_consumers_read_the_new_path_and_tolerate_the_legacy_one():
    """Readers must look at the new location but still accept an old panel.

    Without the legacy fallback, a user who already customised the panel inside
    the package would have it silently ignored rather than migrated.
    """
    skills = _built_skills()
    consumers = ("why", "reflect", "arena", "interrogate")
    for name in consumers:
        text = skills[name]
        assert "pstack-models.json" in text, f"{name} does not read the new panel path"
        assert "legacy `config/models.json`" in text, (
            f"{name} no longer tolerates a panel left in the package by an older install"
        )


def test_shipped_default_panel_still_lives_in_the_package():
    """The default panel is package content; only the user's override moves.

    validate.py asserts the shipped `config/models.json` equals the repo-owned
    panel, so it must keep shipping. This records that the fix does not
    over-reach into removing it.
    """
    panel = REPO / "tools" / "assets" / "model-panel.json"
    assert panel.is_file(), "repo-owned default panel missing"
    assert '"roles"' in panel.read_text(encoding="utf-8")