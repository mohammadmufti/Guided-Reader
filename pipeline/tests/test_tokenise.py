"""
Tokenisation.

Two properties matter. The count must match the workbook's own tokenisation, or
every coverage figure is measured against a different denominator. And the split
must be lossless, because the reading pane rebuilds the text from it.
"""

import re

from tokenise import tokenise, reconstruct, RE_BUKHARI_REF

# Measured from the workbook's `layers` column, which sums to its stated total.
WORKBOOK_LAYERS = {
    "matn": 119_077,
    "zawaid": 6_063,
    "heading_bab": 970,
    "frontmatter": 873,
    "heading_kitab": 224,
}
TOLERANCE = 0.02  # the spec's gate


def test_reconstruction_is_lossless(records):
    """`leading + sum(raw + punctuationAfter)` must rebuild the record exactly."""
    bad = []
    for rec in records["records"]:
        leading, toks = tokenise(rec["textRaw"])
        expected = RE_BUKHARI_REF.sub(" ", rec["textRaw"]).rstrip()
        if reconstruct(leading, toks) != expected:
            bad.append(rec["id"])
    assert not bad, f"{len(bad)} records do not round-trip, first: {bad[:3]}"


def test_token_counts_match_the_workbook(records, expected):
    """The workbook describes ONE text. Comparing another corpus's token
    counts against it is a category error — the fixture key gates this to
    corpora that declare workbook coverage."""
    expected("records.workbook_describes_this_corpus")
    counts = {}
    for rec in records["records"]:
        _, toks = tokenise(rec["textRaw"])
        counts[rec["layer"]] = counts.get(rec["layer"], 0) + len(toks)
    total = sum(counts.values())
    expected = sum(WORKBOOK_LAYERS.values())
    drift = abs(total - expected) / expected
    assert drift < TOLERANCE, f"{total:,} vs {expected:,} ({drift:.3%})"
    # These two reproduce exactly, and have since Phase 1. If they stop, the
    # tokenisation rule has changed rather than merely drifted.
    assert counts["zawaid"] == WORKBOOK_LAYERS["zawaid"]
    assert counts["heading_kitab"] == WORKBOOK_LAYERS["heading_kitab"]


def test_editorial_reference_is_not_a_token():
    """A naive whitespace split overshoots the workbook by 12.6%."""
    _, toks = tokenise("قال النبي. (بخاري: 4)")
    assert all("بخاري" not in t["raw"] for t in toks)
    assert [t["raw"] for t in toks] == ["قال", "النبي"]


def test_only_arabic_bearing_runs_are_tokens():
    """The bare dashes in `- رضي الله عنه -` are punctuation, not words."""
    _, toks = tokenise("- رضي الله عنه - قال")
    assert [t["raw"] for t in toks] == ["رضي", "الله", "عنه", "قال"]
