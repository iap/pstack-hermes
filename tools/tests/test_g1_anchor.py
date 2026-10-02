"""G1's poteto-mode anchor must survive both known upstream phrasings.

The anchor is written against post-Phase-2A text and accepts two sentence
separators, because upstream c47b1284 reworded it while the pinned 93b00b8 is
still the shipping build. These tests drive the converter's real substitution
function (`g1_pm_substitute`) rather than a copy of it, so a regression in the
logic - not just in the literals - fails here instead of surfacing as "anchor not
found" at the next re-pin.

The expected phrases below are written out literally rather than read back from
`convert.G1_PM_HEAD` / `G1_PM_TAILS`. That is deliberate: building the inputs from
the same constants under test means the assertions drift with them and pass no
matter what upstream says. Each string here was copied verbatim out of
`pstack/skills/poteto-mode/SKILL.md` at the two pins, after applying Phase-2A's
`subagent_type` -> "delegate role" substitution:

  93b00b8  "...diverse-model review; respect what the skill prescribes..."
  c47b1284 "...diverse-model review. Respect what the skill prescribes..."

If a future re-pin changes the wording again, these tests fail - which is the
point. They are the tripwire for the next pin bump.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import convert as cv  # noqa: E402

# Verbatim upstream sentence at each supported pin (post-Phase-2A).
UPSTREAM_93B00B8 = (
    "Routed workflow skills (`how`, `why`, `interrogate`, `reflect`, `swarm`) set "
    "their own delegate role for diverse-model review; respect what the skill "
    "prescribes, don't override to `poteto-agent`."
)
UPSTREAM_C47B1284 = (
    "Routed workflow skills (`how`, `why`, `interrogate`, `reflect`, `swarm`) set "
    "their own delegate role for diverse-model review. Respect what the skill "
    "prescribes, don't override to `poteto-agent`."
)
SUPPORTED = (UPSTREAM_93B00B8, UPSTREAM_C47B1284)


def test_constants_still_match_the_upstream_phrases():
    """The converter's constants must equal the real upstream sentences.

    This is the assertion that fails when a future upstream reword leaves the
    anchors stale - the exact situation that blocks a re-pin today.
    """
    matched = next(
        (t for t in cv.G1_PM_TAILS if cv.G1_PM_HEAD + t in UPSTREAM_93B00B8), None
    )
    assert matched is not None, "no accepted tail matches the pinned 93b00b8 wording"
    assert cv.G1_PM_HEAD + matched == UPSTREAM_93B00B8

    matched = next(
        (t for t in cv.G1_PM_TAILS if cv.G1_PM_HEAD + t in UPSTREAM_C47B1284), None
    )
    assert matched is not None, "no accepted tail matches the c47b1284 wording"
    assert cv.G1_PM_HEAD + matched == UPSTREAM_C47B1284


def test_each_supported_phrase_gets_the_escape_hatch():
    for phrase in SUPPORTED:
        out = cv.g1_pm_substitute(phrase)
        assert out is not None, f"anchor did not match: {phrase!r}"
        assert "Exception (hermes port)" in out
        assert out.count("Exception (hermes port)") == 1


def test_upstream_wording_is_preserved_verbatim():
    # The port appends to whatever upstream wrote; it must not normalise the
    # sentence's own punctuation, or the package would drift from upstream.
    for phrase in SUPPORTED:
        out = cv.g1_pm_substitute(phrase)
        assert out is not None
        assert out.startswith(phrase)


def test_substitution_leaves_surrounding_text_intact():
    before = "intro paragraph\n\n"
    after = "\n\ntrailing paragraph\n"
    out = cv.g1_pm_substitute(before + UPSTREAM_93B00B8 + after)
    assert out is not None
    assert out.startswith(before)
    assert out.endswith(after)
    assert before + UPSTREAM_93B00B8 + after != out


def test_unrelated_wording_still_fails_loudly():
    # The tolerance covers the two known phrasings, not a wildcard.
    assert cv.g1_pm_substitute("Some entirely different sentence about routing.") is None


def test_both_tails_are_distinct():
    # Guards against a copy/paste collapse making the tolerance a no-op.
    assert len(set(cv.G1_PM_TAILS)) == len(cv.G1_PM_TAILS) == 2


def test_pass_delegates_to_the_shared_helper():
    """The T7 pass must call g1_pm_substitute, not re-implement the lookup.

    Without this, the helper could pass every test above while the pass kept its
    own single-string logic - the gap Greptile raised on the first revision.
    """
    src = Path(cv.__file__).read_text(encoding="utf-8")
    assert "g1_pm_substitute(pm_text)" in src
    assert "g1_pm_old = next(" not in src
    assert "g1_pm_tail = next(" not in src