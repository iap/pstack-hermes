"""Guard the patch-health workflow (#214).

The fork patches are manual, so the only thing that keeps them honest is a
scheduled check that can fail. These assertions pin the parts that make it a
check rather than a report: it targets a ref, it iterates every patch, and it
exits non-zero when one does not apply.
"""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "patch-health.yml"
DOCS = ROOT / "docs" / "PATCHES.md"


def _triggers(data: dict) -> dict:
    # PyYAML resolves the bare `on:` key to boolean True.
    return data.get("on", data.get(True))


def test_patch_health_runs_weekly_and_on_dispatch():
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    triggers = _triggers(data)
    assert "workflow_dispatch" in triggers, "patch health must be dispatchable"
    crons = [entry["cron"] for entry in triggers["schedule"]]
    assert crons, "patch health must run on a schedule"


def test_patch_health_checks_every_patch_and_fails_on_a_stale_one():
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    job = next(iter(data["jobs"].values()))
    script = "\n".join(step.get("run", "") for step in job["steps"])

    assert 'git clone --depth 1 --branch "$REF"' in script
    assert "patches/*.patch" in script
    assert 'git -C "$target" apply --check' in script
    assert 'exit "$failed"' in script, "a stale patch must fail the job"
    assert "GITHUB_STEP_SUMMARY" in script, "results must be visible without logs"


def test_patch_docs_point_at_the_health_check():
    text = DOCS.read_text(encoding="utf-8")
    assert "patch-health" in text, "docs/PATCHES.md must state where the check lives"
