import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CHECK_PLAN = ROOT / "scripts" / "check-plan.mjs"

RULE = (
    "Tests alone are not sufficient verification. A PR is verified only when its "
    "unit, live, and perf boxes are all checked."
)


def _plan(marker: str) -> str:
    lanes = "\n".join(
        f"- [ ] Lane {n}. Save `lane-{n}.png`. Pass when the marker is shown."
        for n in range(1, 11)
    )
    return "\n".join(
        [
            "# Marker plan",
            "",
            "A plan used to check the trunk marker.",
            "",
            "## How to read this",
            "",
            "One box is one unit of work.",
            "Each names the evidence.",
            "Check a box only when its evidence exists.",
            "See playbooks/ for the rules.",
            RULE,
            "",
            "## Program checklist",
            "",
            "### Arm the program",
            "- [ ] Write `goal.md` with the plan path and the status message.",
            f"- [ ] Read `{marker}skills/poteto-mode/playbooks/opening-a-pr.md` at program start.",
            "- [ ] Arm a 30-minute tick.",
            "",
            "### Spawn owners",
            "- [ ] One owner per PR starts a decision trail.",
            "",
            "### PR mechanics",
            "- [ ] Resolve the forge before the first PR operation.",
            "",
            "### Verdict and merge",
            "- [ ] Record each verdict at the PR head.",
            "",
            "### Boot recipe",
            "- [ ] Start the surface and wait until ready.",
            "",
            "## PR 1 Add the marker",
            "",
            "**Depends on.** None",
            "",
            "**Files.**",
            "- [ ] One file changed.",
            "",
            "**Build.**",
            "- [ ] The build passed.",
            "",
            "**You see.**",
            "- [ ] The marker appears in the plan.",
            "",
            f"**Verify, unit.** {RULE}",
            "- [ ] Unit tests passed.",
            "",
            f"**Verify, live.** {RULE} Ten lanes on `delegation` at the PR head.",
            lanes,
            "",
            f"**Verify, perf.** {RULE}",
            "- [ ] Metric. Seconds.",
            "- [ ] Probe. Twice.",
            "- [ ] Baseline. Trunk.",
            "- [ ] Rule. Under ten.",
            "",
            "**Review gate.** None. PR 1 is not review-gated.",
            "",
            "**Merge.**",
            "- [ ] Squash landed.",
            "",
            "## Close the program",
            "",
            "Record the final verdict.",
            "",
            "## Appendix A Prototype evidence",
            "",
            "No prototype evidence was needed.",
            "",
        ]
    )


def _check(tmp_path, marker: str):
    plan = tmp_path / "plan.md"
    plan.write_text(_plan(marker), encoding="utf-8")
    return subprocess.run(
        ["node", str(CHECK_PLAN), str(plan)],
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    "marker",
    ["git show refs/remotes/<trunk-remote>/HEAD:", "git show origin/HEAD:", "git show origin/master:", "git show origin/main:"],
)
def test_any_trunk_ref_marker_passes_checker(tmp_path, marker):
    result = _check(tmp_path, marker)
    assert result.returncode == 0, result.stderr + result.stdout


@pytest.mark.parametrize(
    "marker",
    ["git show HEAD:", "git show refs/heads/topic:", "Read the trunk playbook from disk."],
)
def test_non_remote_trunk_read_fails_checker(tmp_path, marker):
    plan = tmp_path / "plan.md"
    plan.write_text(_plan(marker), encoding="utf-8")
    result = subprocess.run(
        ["node", str(CHECK_PLAN), str(plan)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "Program checklist lacks" in result.stderr
