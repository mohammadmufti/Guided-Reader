"""
Buckwalter gloss parsing.

The raw string must never reach a reader — `the + prayer;salat + [fem.sg.]` is
not an answer. Parsing happens once at build time so the client cannot render it
by accident, which makes this the only place the parse is checked.
"""

import pytest

from gloss import parse_gloss


def test_every_gloss_parses(surface):
    """21,028 glosses. A parse failure means a word loses its meaning entirely."""
    import pandas as pd

    glosses = [str(r["gloss_msa"]) for r in surface if pd.notna(r["gloss_msa"])]
    failures = [g for g in glosses if parse_gloss(g) is None]
    empty = [g for g in glosses if (p := parse_gloss(g)) and not p["senses"]]
    assert not failures, f"{len(failures)} unparseable, first: {failures[:3]}"
    assert not empty, f"{len(empty)} parsed to an empty sense list, first: {empty[:3]}"
    assert len(glosses) > 20_000, f"only {len(glosses)} glosses — is the sheet right?"


def test_no_markup_survives(surface):
    """Segment markers, feature brackets and POS tags must all be consumed."""
    import pandas as pd

    for r in surface:
        if pd.isna(r["gloss_msa"]):
            continue
        p = parse_gloss(str(r["gloss_msa"]))
        blob = " ".join(p["senses"])
        blob += " ".join(s for slot in p["before"] + p["after"] for s in slot["senses"])
        for marker in ("___", " + ", "<", "["):
            assert marker not in blob, f"{marker!r} leaked from {r['gloss_msa']!r}"


@pytest.mark.parametrize(
    "raw,stem",
    [
        # Stem in the middle.
        ("the + prayer;salat + [fem.sg.]", ["prayer", "salat"]),
        # Stem LAST, after two clitics — `I` is the imperfect subject prefix,
        # not lexical content. A positional rule gets this wrong.
        ("and + I + leave;quit", ["leave", "quit"]),
        # Empty proclitic slot.
        ("___ + burn;brand + [fem.sg.]", ["burn", "brand"]),
        ("he/it + guide;direct;lead", ["guide", "direct", "lead"]),
        ("and + messenger (Muhammad) + its/his", ["messenger (Muhammad)"]),
    ],
)
def test_stem_identification(raw, stem):
    assert parse_gloss(raw)["senses"] == stem


def test_features_are_hoisted():
    p = parse_gloss("the + prayer;salat + [fem.sg.]")
    assert p["features"] == ["fem", "sg"]


def test_clitic_chain_is_kept():
    p = parse_gloss("and + for + him/it to + cause;bring about")
    assert p["senses"] == ["cause", "bring about"]
    assert [s["senses"] for s in p["before"]] == [["and"], ["for"], ["him/it to"]]
