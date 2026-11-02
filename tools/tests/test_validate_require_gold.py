"""--require-gold: an unavailable loader must never look like a pass.

CI runs `validate.py --require-gold`; without it, a runner with no hermes
install degrades to the static mirror and exits 0, which is how the GOLD layer
went unenforced for the entire history of this repo.
"""

import validate


def code(**overrides):
    base = {
        "static_failed": False,
        "gold_available": True,
        "load_available": True,
        "gold_ok": True,
        "load_ok": True,
        "require_gold": False,
    }
    base.update(overrides)
    return validate.resolve_exit_code(**base)


def test_clean_run_is_zero():
    assert code() == 0


def test_static_failure_is_one_even_when_gold_passed():
    assert code(static_failed=True) == 1


def test_gold_ran_and_failed_is_two():
    assert code(gold_ok=False) == 2
    assert code(load_ok=False) == 2


def test_unavailable_loader_still_skips_by_default():
    # Contributor machines without hermes keep the documented behaviour.
    assert code(gold_available=False, load_available=False) == 0


def test_unavailable_loader_fails_when_required():
    assert code(gold_available=False, load_available=False, require_gold=True) == 3


def test_static_failure_outranks_a_missing_loader():
    assert code(
        static_failed=True, gold_available=False, load_available=False, require_gold=True
    ) == 1