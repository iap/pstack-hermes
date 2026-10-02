"""G1's poteto-mode anchor must survive both known upstream phrasings.

The anchor is written against post-Phase-2A text and accepts two sentence
separators, because upstream c47b1284 reworded it while the pinned 93b00b8 is
still the shipping build. These tests pin that tolerance so a future edit cannot
quietly reduce it back to a single phrasing - the failure that would only surface
as "anchor not found" at the next re-pin.

The constants live inside apply_phase1_transforms(), so the literals are mirrored
here and checked against the real source text. That keeps the test honest without
restructuring the converter purely for testability: assert_mirrored_literals
fails if the source strings ever diverge from what this file assumes.
"""

import re
import sys
from pathlib import Path

CONVERT = Path(__file__).resolve().parents[1] / "convert.py"
sys.path.insert(0, str(CONVERT.parent))
import convert as cv  # noqa: E402

HEAD = (
    "Routed workflow skills (`how`, `why`, `interrogate`, `reflect`, `swarm`) set "
    "their own delegate role for diverse-model review"
)
TAILS = (
    "; respect what the skill prescribes, don't override to `poteto-agent`.",
    ". Respect what the skill prescribes, don't override to `poteto-agent`.",
)
ESCAPE = (
    " Exception (hermes port): for surgical, fully-specified edits to files "
    "already resident in your context, implement in-thread and use a "
    "`delegate_task` leaf as the independent reviewer of the diff instead "
    "of the author."
)


def test_mirrored_literals_still_match_the_converter():
    """The mirrored constants must be the ones the converter actually uses."""
    src = CONVERT.read_text(encoding="utf-8")
    flat = re.sub(r'"\s*\n\s*"', "", src)  # join implicit string concatenation
    assert HEAD.replace('"', "'") in flat.replace('"', "'") or HEAD in src
    for tail in TAILS:
        assert tail in src, f"converter no longer contains tail: {tail!r}"
    assert "Exception (hermes port)" in src


def _apply(text: str) -> str | None:
    """Mirror the converter's G1_PM call site."""
    matched = next((HEAD + t for t in TAILS if HEAD + t in text), None)
    if matched is None:
        return None
    tail = next(t for t in TAILS if matched.endswith(t))
    return text.replace(matched, HEAD + tail + ESCAPE, 1)


def test_old_pin_semicolon_form_is_matched():
    out = _apply(HEAD + TAILS[0])
    assert out is not None, "93b00b8 phrasing must still match"
    assert "Exception (hermes port)" in out


def test_new_pin_capitalised_form_is_matched():
    out = _apply(HEAD + TAILS[1])
    assert out is not None, "c47b1284 phrasing must match"
    assert "Exception (hermes port)" in out


def test_escape_hatch_is_added_exactly_once():
    out = _apply(HEAD + TAILS[0])
    assert out is not None
    assert out.count("Exception (hermes port)") == 1


def test_original_separator_is_preserved():
    # The port appends to whatever upstream wrote; it must not normalise the
    # sentence's own punctuation, or the package would drift from upstream.
    for tail in TAILS:
        out = _apply(HEAD + tail)
        assert out is not None
        assert out.startswith(HEAD + tail)


def test_unrelated_wording_still_fails_loudly():
    # The tolerance covers one known rewording, not a wildcard: text that is not
    # the G1 sentence must not be silently "matched".
    assert _apply("Some entirely different sentence about routing.") is None


def test_both_tails_are_distinct():
    # Guards against a copy/paste collapse making the tolerance a no-op.
    assert len(set(TAILS)) == len(TAILS) == 2


def test_converter_still_exposes_the_tolerant_call_site():
    """The converter must use the two-tail lookup, not a single exact string."""
    src = CONVERT.read_text(encoding="utf-8")
    assert "G1_PM_TAILS" in src
    assert "G1_PM_OLD" not in src, "single-string G1 anchor is back"
    assert isinstance(cv.ConvertError("x"), cv.ConvertError)