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
AGREEMENT_FLOOR = 85.0  # measured 92.3% on all 17,939 comparable forms
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
    A CATASTROPHE floor, not a conformity target. The workbook's morphology
    is itself qalsadi-derived, so this number measures distance from the
    analysed layer's own ancestry — and it is EXPECTED to fall when a better
    provider corrects the shared mistakes. It did: 92.3% under qalsadi
    alone, 90.1% after CAMeL's adoption, with Lane siding with the
    divergence 818:321 (reports/camel-bakeoff.md). The floor below exists
    only to catch a provider gone haywire; the accuracy question belongs to
    the gold sample.

    Compared on `root_key`, which folds bare hamza. Comparing on `normalise`
    instead over-reports disagreement because ءني and أني are the same root
    written two ways.
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


def test_the_khattab_class_is_closed():
    """
    الخطاب shipped with root خصب because the primary was chosen by ARABIC
    ALPHABET among the dictionary's candidate rows (sorted(roots)[0]). These
    forms pin the fix: vocalisation decides, majority next, Lane next, and
    an unresolved tie says so instead of pretending.
    """
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parent.parent / "build" / "morphology" / "analyses.json"
    if not path.exists():
        import pytest
        pytest.skip("run pipeline/analyse.py first")
    d = json.loads(path.read_text(encoding="utf-8"))

    from normalise import normalise, root_key

    # Keys are the workbook's vocalised forms; combining-mark ORDER in a
    # source-code literal need not match the workbook's byte-for-byte even
    # when they render identically. Look up through the normaliser instead.
    by_norm: dict[str, dict] = {}
    for k, v in d.items():
        if v:
            by_norm.setdefault(normalise(k), v)

    expected = {
        "الخطاب": "خطب",   # was خصب — an arramooz bad row won by alphabet
        "مصر": "مصر",       # was صرر — genuine homograph, vowels decide
        "غدا": "غدو",       # was غدد
        "الغد": "غدو",
    }
    for form, want in expected.items():
        got = by_norm.get(form)
        assert got and got.get("root"), f"{form}: no analysis"
        assert root_key(got["root"]) == root_key(want), \
            f"{form}: {got['root']} (basis {got.get('rootBasis')}), wanted {want}"
        assert got.get("rootBasis"), f"{form}: choice carries no basis"
