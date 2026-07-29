"""
Stem recovery, and its accuracy.

409 forms carry pos=particle, a one-letter lemma and no root because the
supplied analyser kept a proclitic and discarded the word. The recoverer strips
affixes and looks the residue up in this corpus's own lexicon.

The accuracy figure is the point of this file. It was 85.4% before the NaN
filter, the gloss constraint and the corroboration check; it is asserted here so
that a change which quietly undoes one of them fails the build instead of
degrading a reader's page.
"""

import pandas as pd
import pytest

from gloss import parse_gloss
from morphology import Recoverer
from normalise import normalise

ACCURACY_FLOOR = 97.0  # measured 98.0%; this is a floor, not the value
MIN_OPINIONS = 3_000   # a rule that fires rarely can be accurate and useless


@pytest.fixture(scope="module")
def recoverer(by_search_key):
    rows = {k: [{**r, "match_id": str(r["match_id"])} for r in v] for k, v in by_search_key.items()}
    return Recoverer(rows)


def _held_out(recoverer, surface):
    """
    Forms whose root the workbook already records AND whose gloss says they
    carry affixes — the population the recoverer actually serves. Hide the exact
    match so a strip is forced, then compare.
    """
    ok = bad = 0
    wrong = []
    for r in surface:
        if not isinstance(r.get("root"), str) or not r["root"].strip():
            continue
        if r.get("pos") in (None, "particle"):
            continue
        g = parse_gloss(r["gloss_msa"]) if pd.notna(r.get("gloss_msa")) else None
        if not g:
            continue
        npro, nenc = len(g["before"]), len(g["after"])
        if npro == 0 and nenc == 0:
            continue
        got = recoverer.recover(
            str(r["search_key"]),
            unvocalized=str(r["unvocalized"]),
            n_proclitics=npro,
            n_enclitics=nenc,
            stem_senses=g["senses"],
            exclude_self=True,
        )
        if got is None:
            continue
        if got.root == str(r["root"]):
            ok += 1
        else:
            bad += 1
            if len(wrong) < 5:
                wrong.append((r["vocalized"], r["root"], got.root))
    return ok, bad, wrong


def test_held_out_accuracy(recoverer, surface):
    ok, bad, wrong = _held_out(recoverer, surface)
    total = ok + bad
    assert total >= MIN_OPINIONS, f"only offered {total} opinions"
    accuracy = 100 * ok / total
    assert accuracy >= ACCURACY_FLOOR, (
        f"{accuracy:.1f}% on {total:,} held-out forms "
        f"(floor {ACCURACY_FLOOR}%). Examples: {wrong}"
    )


def test_recovers_the_motivating_cases(recoverer, by_search_key):
    """
    The words that prompted this module. Each must come back with the right
    root, via a stem attested elsewhere in the same corpus.
    """
    expected = {"وليحدث": ("حدث", "يحدث"), "فليبايعني": ("بيع", "يبايع")}
    for key, (root, via) in expected.items():
        row = max(by_search_key[key], key=lambda r: r["freq"])
        g = parse_gloss(row["gloss_msa"])
        got = recoverer.recover(
            key,
            unvocalized=str(row["unvocalized"]),
            n_proclitics=len(g["before"]),
            n_enclitics=len(g["after"]),
            stem_senses=g["senses"],
        )
        assert got is not None, f"{key} not recovered"
        assert got.root == root and got.stem == via, f"{key}: {got.root} via {got.stem}"


def test_stays_silent_when_the_stem_is_unattested(recoverer, by_search_key):
    """
    `سَيَفْقِدُونَنِي` needs `يفقدون`, which does not occur in this book.
    Silence is the correct output; a guess would be worse than nothing.
    """
    row = by_search_key["سيفقدونني"][0]
    g = parse_gloss(row["gloss_msa"])
    got = recoverer.recover(
        "سيفقدونني",
        unvocalized=str(row["unvocalized"]),
        n_proclitics=len(g["before"]),
        n_enclitics=len(g["after"]),
        stem_senses=g["senses"],
    )
    assert got is None


def test_null_roots_are_never_offered_as_evidence(recoverer):
    """
    A pandas NaN is a float and floats are truthy, so `if row["root"]` let every
    root-less row through and the analyser answered with root=nan. That bug cost
    12 points of accuracy on its own.
    """
    for row in recoverer.by_key.values():
        assert isinstance(row["root"], str) and row["root"].strip()
