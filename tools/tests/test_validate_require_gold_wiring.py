"""Subprocess test: main() actually wires --require-gold (issue #130 item 2).

Unit tests cover resolve_exit_code in isolation; this pins the CLI wiring so
that deleting `require_gold=args.require_gold` from the resolve_exit_code call
fails the suite.
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_require_gold_wiring_via_subprocess(tmp_path):
    # Point HERMES_HOME at an empty dir so the loader is unavailable.
    empty_home = tmp_path / "empty-hermes"
    empty_home.mkdir()
    env = dict(os.environ)
    env["HERMES_HOME"] = str(empty_home)
    # Ensure no stray hermes on PATH resolves; use the repo's own python.
    proc = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "validate.py"),
         "--package", str(ROOT), "--require-gold"],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    # With --require-gold and no hermes available, the output must say
    # "REQUIRED but UNAVAILABLE" (proves the flag is wired into main()).  The
    # exit code is 3 when static checks pass and 1 when they fail first, so
    # accept either; a silent 0 (flag ignored) is the regression we guard.
    assert "REQUIRED but UNAVAILABLE" in (proc.stdout + proc.stderr), (
        f"--require-gold not wired?\n"
        f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
    )
    assert proc.returncode in (1, 3), (
        f"expected exit 1 or 3, got {proc.returncode}\n"
        f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
    )