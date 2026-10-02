"""G1's poteto-mode anchor must survive both known upstream phrasings.

The anchor is written against post-Phase-2A text and accepts two sentence
separators, because upstream c47b1284 reworded it while the pinned 93b00b8 is
still the shipping build. These tests drive the converter's real substitution
function (`g1_pm_substitute`) rather than a copy of it, so a regression in the
logic - not just in the literals - fails here instead of surfacing as "anchor not
found" at the next re-pin.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import convert as cv  # noqa: E402


def test_old_pin_semicolon_form_is_matched():
    out = cv.g1_pm_substitute(cv.G1_PM_HEAD + cv.G1_PM_TAILS[0])
    assert out is not None, "93b00b8 phrasing must still match"
    assert "Exception (hermes port)" in out


def test_new_pin_capitalised_form_is_matched():
    out = cv.g1_pm_substitute(cv.G1_PM_HEAD + cv.G1_PM_TAILS[1])
    assert out is not None, "c47b1284 phrasing must match"
    assert "Exception (hermes port)" in out


def test_escape_hatch_is_added_exactly_once():
    for tail in cv.G1_PM_TAILS:
        out = cv.g1_pm_substitute(cv.G1_PM_HEAD + tail)
        assert out is not None
        assert out.count("Exception (hermes port)") == 1


def test_original_separator_is_preserved():
    # The port appends to whatever upstream wrote; it must not normalise the
    # sentence's own punctuation, or the package would drift from upstream.
    for tail in cv.G1_PM_TAILS:
        out = cv.g1_pm_substitute(cv.G1_PM_HEAD + tail)
        assert out is not None
        assert out.startswith(cv.G1_PM_HEAD + tail)


def test_substitution_leaves_surrounding_text_intact():
    before = "intro paragraph\n\n"
    after = "\n\ntrailing paragraph\n"
    src = before + cv.G1_PM_HEAD + cv.G1_PM_TAILS[0] + after
    out = cv.g1_pm_substitute(src)
    assert out is not None
    assert out.startswith(before)
    assert out.endswith(after)
    assert src[len(before) : -len(after)] != out[len(before) : -len(after)]


def test_unrelated_wording_still_fails_loudly():
    # The tolerance covers one known rewording, not a wildcard: text that is not
    # the G1 sentence must not be silently "matched".
    assert cv.g1_pm_substitute("Some entirely different sentence about routing.") is None


def test_both_tails_are_distinct():
    # Guards against a copy/paste collapse making the tolerance a no-op.
    assert len(set(cv.G1_PM_TAILS)) == len(cv.G1_PM_TAILS) == 2


def test_pass_delegates_to_the_shared_helper():
    """The T7 pass must call g1_pm_substitute, not re-implement the lookup.

    Without this, the helper could pass every test above while the pass kept its
    own single-string logic - the exact gap Greptile raised on the first
    revision of this PR.
    """
    src = Path(cv.__file__).read_text(encoding="utf-8")
    assert "g1_pm_substitute(pm_text)" in src
    # The old inline two-step form must be gone from the pass body.
    assert "g1_pm_old = next(" not in src
    assert "g1_pm_tail = next(" not in src