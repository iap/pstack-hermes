"""Structural guards for the two workflow findings of the PR #67 review.

1. Drift watchers: the upsert step must be conditioned on the check step's
   `drift` output, and that output may only be written on the path that also
   writes the drift body. Splitting the upsert into its own step silently
   dropped the guard the single-script version had (the no-drift `exit 0`s
   stop a step, not a job), which made every no-drift run fail on a body file
   that was never written - the common case, latent only while upstream drift
   keeps the body-writing path active.

2. ci.yml concurrency: non-PR runs must not share a concurrency group with
   any other run. cancel-in-progress protects only started runs; by default a
   newer pending run cancels an older pending one in the same group, so a main
   push could be cancelled before it started and skip verify-determinism.
"""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"

WATCHERS = ("upstream-drift-watch.yml", "model-drift-watch.yml")
UPSERT_ACTION = "./.github/actions/drift-issue-upsert"
GUARD = "steps.check.outputs.drift == 'true'"
BODY_MARKER = '> "$RUNNER_TEMP/drift-body.md"'
OUTPUT_WRITE = 'echo "drift=true" >> "$GITHUB_OUTPUT"'


def _steps(name: str) -> list:
    data = yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))
    jobs = data["jobs"]
    assert len(jobs) == 1, f"{name}: expected exactly one job"
    return next(iter(jobs.values()))["steps"]


def test_upsert_step_is_guarded_in_both_watchers():
    for name in WATCHERS:
        steps = _steps(name)
        check_idx = [i for i, s in enumerate(steps) if s.get("id") == "check"]
        upsert_idx = [i for i, s in enumerate(steps) if s.get("uses") == UPSERT_ACTION]
        assert len(check_idx) == 1, f"{name}: expected one step with id 'check'"
        assert len(upsert_idx) == 1, f"{name}: expected exactly one upsert step"
        assert check_idx[0] < upsert_idx[0], f"{name}: upsert must run after the check"
        guard = steps[upsert_idx[0]].get("if")
        assert guard == GUARD, f"{name}: upsert step must be guarded by: {GUARD}"


def test_drift_output_is_written_only_after_the_body_file():
    for name in WATCHERS:
        check = next(s for s in _steps(name) if s.get("id") == "check")
        script = check["run"]
        assert script.count(OUTPUT_WRITE) == 1, (
            f"{name}: expected exactly one drift output write"
        )
        body_at = script.index(BODY_MARKER)
        write_at = script.index(OUTPUT_WRITE)
        assert write_at > body_at, (
            f"{name}: the drift output must be written after the body file, "
            "or a no-drift early exit could still unlock the upsert"
        )
        pos = 0
        while (pos := script.find("exit 0", pos)) != -1:
            assert pos < write_at, (
                f"{name}: no 'exit 0' is expected after the drift output write"
            )
            pos += 1


def test_ci_concurrency_keeps_non_pr_runs_whole():
    data = yaml.safe_load((WORKFLOWS / "ci.yml").read_text(encoding="utf-8"))
    concurrency = data["concurrency"]
    group = concurrency["group"]
    assert "github.run_id" in group, (
        "non-PR runs must take a per-run concurrency group"
    )
    assert "github.event_name == 'pull_request'" in group, (
        "the shared group must be limited to pull_request runs"
    )
    assert "github.ref" in group, "PR runs must keep sharing the per-ref group"
    cancel = concurrency["cancel-in-progress"].strip()
    assert cancel == "${{ github.event_name == 'pull_request' }}", (
        f"cancel-in-progress must stay PR-only, got {cancel!r}"
    )
