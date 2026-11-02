"""--require-gold: an unavailable loader must never look like a pass.

CI runs `validate.py --require-gold`; without it, a runner with no hermes
install degrades to the static mirror and exits 0, which is how the GOLD layer
went unenforced for the entire history of this repo.

The state split matters too: "the environment exists but the loader could not be
driven" used to be reported as "the loader ran and rejected the package", which
sends a reader hunting a defect in the package instead of the harness.
"""

import validate


def code(**overrides):
    base = {
        "static_failed": False,
        "loader_state": "ran",
        "loader_ok": True,
        "require_gold": False,
    }
    base.update(overrides)
    return validate.resolve_exit_code(**base)


def state(gold_status, load_status):
    return validate.loader_state({"status": gold_status}, {"status": load_status})


# --- state classification -------------------------------------------------


def test_both_checks_returning_structured_output_means_ran():
    assert state("ok", "ok") == "ran"
    assert state("ok", "nonzero-exit") == "ran"
    assert state("nonzero-exit", "nonzero-exit") == "ran"


def test_import_or_subprocess_failure_means_broken():
    assert state("import-failed", "ok") == "broken"
    assert state("ok", "no-json-stdout") == "broken"
    assert state("error", "error") == "broken"


def test_missing_environment_means_unavailable():
    assert state("unavailable", "unavailable") == "unavailable"
    # A skipped load (package dir missing) is not a broken harness.
    assert state("unavailable", "skipped") == "unavailable"


# --- exit codes -----------------------------------------------------------


def test_clean_run_is_zero():
    assert code() == 0


def test_static_failure_is_one_even_when_the_loader_passed():
    assert code(static_failed=True) == 1


def test_loader_ran_and_rejected_is_two_with_or_without_the_flag():
    assert code(loader_ok=False) == 2
    assert code(loader_ok=False, require_gold=True) == 2


def test_absent_loader_skips_by_default_and_fails_when_required():
    assert code(loader_state="unavailable") == 0
    assert code(loader_state="unavailable", require_gold=True) == 3


def test_broken_loader_never_skips_silently():
    # Present-but-broken is a harness failure, not a reason to report a pass.
    assert code(loader_state="broken") == 2
    assert code(loader_state="broken", require_gold=True) == 3


def test_static_failure_outranks_a_missing_loader():
    assert code(static_failed=True, loader_state="unavailable", require_gold=True) == 1
    assert code(static_failed=True, loader_state="broken", require_gold=True) == 1