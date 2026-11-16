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

    assert 'git clone --depth 1 --branch "$TARGET"' in script
    assert "patches/*.patch" in script
    assert "patches/archive/*.patch" in script
    assert "refusing a vacuous pass" in script
    assert 'git -C "$target" apply --check' in script
    assert 'exit "$failed"' in script, "a stale patch must fail the job"
    assert "GITHUB_STEP_SUMMARY" in script, "results must be visible without logs"


def test_patch_health_covers_main_and_the_latest_release_by_default():
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    job = next(iter(data["jobs"].values()))
    matrix = job["strategy"]["matrix"]["ref"]

    assert "main" in matrix
    assert "latest" in matrix
    script = "\n".join(step.get("run", "") for step in job["steps"])
    assert "git ls-remote --tags" in script, "latest must resolve a release tag, not a branch"


def test_patch_summary_names_the_failing_hunk():
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    job = next(iter(data["jobs"].values()))
    script = "\n".join(step.get("run", "") for step in job["steps"])

    assert "failing hunk" in script
    assert "first_line" in script
    assert "$first_line" in script
    assert "**FAIL**" in script



def test_patch_docs_point_at_the_health_check():
    text = DOCS.read_text(encoding="utf-8")
    assert "patch-health" in text, "docs/PATCHES.md must state where the check lives"


def test_latest_resolution_cannot_die_of_sigpipe():
    """`head -1` closes the pipe; under `set -o pipefail` that is exit 141.

    The first dispatch of this workflow failed exactly that way, before it
    checked a single patch. The resolver must read the whole stream.
    """
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    job = next(iter(data["jobs"].values()))
    resolve = next(s for s in job["steps"] if s.get("name") == "Resolve target ref")
    script = resolve["run"]

    assert "set -euo pipefail" in script
    assert "| sed -n '1s#.*refs/tags/##p')" in script
    assert "| head -1" not in script
