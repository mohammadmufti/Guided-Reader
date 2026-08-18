"""The diacritic-compatibility test that gates every CAMeL reading — with
the two word-panel bugs it shipped pinned as regressions.

Both bugs were the same shape from opposite directions. صلى (the taslya
formula, unvowelled in its witness) REJECTED صَلَّى for a shadda the bare
form never denied, and the reader was told the formula means "roast".
بْنِ (sukun written on the ب) correctly rejected the coffee bean بُنٌّ —
and the old `or analyses` fallback in camel() then resurrected the whole
incompatible set, whose best-supported lemma was the coffee bean, glossed
"coffee beans" beside the donor's "son". The rule that fixes both without
breaking either: a mark only one side wrote is not evidence — INCLUDING
shadda — but a letter the form vocalised is testimony about that letter.
"""
import pytest

from analyse import compatible


def test_bare_form_admits_shadda_it_never_denied():
    assert compatible("صلى", "صَلَّى"), "the pray reading must be admissible"
    assert compatible("صلى", "صَلَى"), "so must roast — ranking decides, not a veto"


def test_vocalised_letter_is_testimony():
    assert not compatible("بْنِ", "بُنٌّ"), "sukun vs damma rejects coffee"
    assert not compatible("بَنَّ", "بَن"), \
        "a shadda the form WROTE and the candidate lacks is evidence too"
    assert compatible("بْنِ", "بْن"), "the ibn spelling stays compatible"


def test_prior_distinctions_survive():
    assert not compatible("أَبِي", "أَبَى")
    assert not compatible("هِجْرَة", "هُجْرَة")
    assert compatible("بَعَثَكَ", "بَعَث"), "clitics sit outside the skeleton"


def test_lemma_and_gloss_never_come_from_the_incompatible_set():
    """The fallback split, asserted structurally: roots may fall back to the
    full analysis set when nothing is compatible (a DB marking convention
    must not veto a correct root), but the lemma/gloss support loop reads
    the STRICT set only."""
    import inspect, analyse
    src = inspect.getsource(analyse)
    i = src.index("keep_strict = [a for a in analyses")
    j = src.index("lexOut", i)
    block = src[i:j]
    assert "for a in keep_strict:" in block, \
        "lex/gloss support must iterate the compatible-only set"
    assert "keep = keep_strict or analyses" in block, \
        "roots keep their measured fallback"
