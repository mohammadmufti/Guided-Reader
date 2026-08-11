"""
Buckwalter gloss parsing.

The raw string must never reach a reader — `the + prayer;salat + [fem.sg.]` is
not an answer. Parsing happens once at build time so the client cannot render it
by accident, which makes this the only place the parse is checked.
"""

import pytest

from pathlib import Path as _Path

ROOT = _Path(__file__).resolve().parent.parent

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


def test_underscores_are_spacing_not_letters():
    """Buckwalter writes a multi-word sense with underscores.

    `kneeling_down`, `make_a_pilgrimage`. That is the encoding of a space, and
    a reader should never see it. The workbook was written with real spaces, so
    this only showed up once the analyser's glosses started being displayed.
    """
    assert parse_gloss("kneeling_down;genuflection")["senses"] == [
        "kneeling down", "genuflection"]
    assert parse_gloss("make_a_pilgrimage;confute")["senses"] == [
        "make a pilgrimage", "confute"]
    # A bare placeholder stays empty rather than becoming a space.
    assert parse_gloss("___") is None or parse_gloss("___")["senses"] == []


def test_a_clitic_chain_is_not_a_list_of_senses():
    """`+` separates clitic glosses from the stem, not one sense from another.

    CAMeL's `stemgloss` usually gives the stem alone, but not always:
    `بِسْمِ` comes back as `in;by_+_(the)_Name_of`, where `in;by` glosses the
    attached bi- and only the last segment is the word. Unsplit, the chain
    became the sense list, and a curated `in/by` sat beside a quick
    `in, by + (the) Name of` — the same meaning, unrecognised as such.
    """
    assert parse_gloss("in;by_+_(the)_Name_of")["senses"] == ["(the) Name of"]
    assert parse_gloss("to;for_+_God;Allah")["senses"] == ["God", "Allah"]
    # A gloss with no chain is untouched.
    assert parse_gloss("prayer;salat")["senses"] == ["prayer", "salat"]


def test_one_implementation_decides_whether_two_glosses_agree():
    """It was written twice and the two drifted.

    Once in Python for the comparison report, once in TypeScript to decide
    whether the panel shows both glosses. Duplicate glosses reappeared when two
    corpora were added, because only one of the two knew about clitic chains.

    The build decides now — `glossQuick` is null where it duplicates the
    curated gloss — and the panel only checks whether the field is there.
    """
    from gloss import says_the_same
    assert says_the_same(parse_gloss("prayer;salat"), parse_gloss("prayer;salat"))
    # The workbook's `a/b` against the analyser's separate senses.
    assert says_the_same(parse_gloss("on/above"), parse_gloss("on;above"))
    # A real disagreement stays one.
    assert not says_the_same(parse_gloss("be frail;be fragile"), parse_gloss("it;they;she"))
    # And nothing to compare is not agreement.
    assert not says_the_same(None, parse_gloss("prayer"))

    panel = (ROOT.parent / "web/src/components/WordPanel.tsx").read_text(encoding="utf-8")
    assert "sameMeaning" not in panel, "the client must not compare glosses itself"
