"""
The analysers run directly.

The workbook's own README says its morphology is `qalsadi` reconciled against
Buckwalter/AraMorph — so this is not a second opinion, it is the same one
without the lossy cache in between. These tests pin the two figures that
justify using it.
"""

import json
from pathlib import Path

import pytest

from normalise import root_key

BUILD = Path(__file__).resolve().parent.parent / "build"
AGREEMENT_FLOOR = 91.0  # measured 92.3% on all 17,939 comparable forms
COVERAGE_FLOOR = 85.0   # measured 87.9% of forms resolve to a root


@pytest.fixture(scope="module")
def analyses():
    path = BUILD / "morphology" / "analyses.json"
    if not path.exists():
        pytest.skip("run pipeline/analyse.py first")
    return json.loads(path.read_text(encoding="utf-8"))


def test_root_coverage(analyses):
    with_root = sum(1 for v in analyses.values() if v.get("root"))
    share = 100 * with_root / len(analyses)
    assert share >= COVERAGE_FLOOR, f"{share:.1f}% of forms resolve to a root"


def test_agrees_with_the_workbook(analyses, surface):
    """
    Compared on `root_key`, which folds bare hamza. Comparing on `normalise`
    instead reports 92.9% because ءني and أني are the same root written two
    ways — a measurement error, not a disagreement.
    """
    agree = disagree = 0
    for row in surface:
        wb = row.get("root")
        if not isinstance(wb, str) or not wb.strip():
            continue
        got = analyses.get(str(row["vocalized"]))
        if not got or not got.get("root"):
            continue
        if root_key(str(got["root"])) == root_key(wb):
            agree += 1
        else:
            disagree += 1
    total = agree + disagree
    assert total > 10_000, f"only {total} forms comparable"
    share = 100 * agree / total
    assert share >= AGREEMENT_FLOOR, f"{share:.1f}% agreement on {total:,} forms"


@pytest.mark.parametrize(
    "search_key,lemma,root",
    [
        # Forms the workbook recorded as particles with no root at all.
        ("وليحدث", "حدث", "حدث"),
        ("سيفقدونني", "فقد", "فقد"),
        ("فليبايعني", "بايع", "بيع"),
    ],
)
def test_recovers_the_lost_stems(analyses, surface, search_key, lemma, root):
    """
    Looked up through the workbook's own `vocalized` value rather than a
    hand-typed literal: diacritic ORDER is not normalised, so a string that
    renders identically can differ byte for byte and miss.
    """
    forms = [str(r["vocalized"]) for r in surface if str(r["search_key"]) == search_key]
    assert forms, f"{search_key} not in the workbook"
    got = next((analyses[f] for f in forms if f in analyses), None)
    assert got, f"{search_key} not analysed"
    assert got["lemma"] == lemma
    assert root_key(got["root"] or "") == root_key(root)


def test_both_dictionary_tables_are_queried(analyses):
    """
    Verbs and nouns are separate dictionaries: بايع resolves only in verbs,
    صلاة and بنيان only in nouns. Querying one halves coverage silently.
    """
    verb = next(v for v in analyses.values() if v.get("lemma") == "بايع")
    assert root_key(verb["root"] or "") == root_key("بيع")  # only in the verbs table
    noun = next(v for v in analyses.values() if v.get("lemma") == "صلاة")
    assert root_key(noun["root"] or "") == root_key("صلو")  # only in the nouns table
