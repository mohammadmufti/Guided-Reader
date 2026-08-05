"""
Segmentation, on both corpora.

The second corpus is the whole basis of the generalisation claim, and it is
exercised nowhere else. `segment.py` contains no Arabic string and no
corpus-specific regex; if that stops being true, this is what says so.
"""

import pytest

import re

RESIDUALS = {
    "PageV": re.compile(r"PageV"),
    "ms###": re.compile(r"\bms\d+\b"),
    "page bracket": re.compile(r"\[\s*ص\s*:"),
    "section marker": re.compile(r"###"),
    "shamela div": re.compile(r"<div"),
    "continuation": re.compile(r"~~"),
}


def _residuals(doc):
    hits = []
    for rec in doc["records"]:
        blob = rec["textRaw"] + " " + (rec["zawaidNote"] or "")
        for name, pat in RESIDUALS.items():
            if pat.search(blob):
                hits.append((rec["id"], name))
    return hits


def test_record_counts(records, expected):
    """The pins live in fixtures/{corpus}.yaml — see conftest."""
    by_layer = {}
    for r in records["records"]:
        by_layer[r["layer"]] = by_layer.get(r["layer"], 0) + 1
    assert len(records["records"]) == expected("records.total")
    assert by_layer == expected("records.by_layer")


def test_every_display_number_resolves(records, expected):
    """
    Invariant: every display number in the covered range resolves to a real
    record, with no gaps. The range itself is the corpus's pin.
    """
    top = expected("records.display_number_max")
    numbers = sorted(n for r in records["records"] for n in r["numbersCovered"])
    assert numbers == list(range(1, top + 1))
    idx = records["navigation"]["numberIndex"]
    assert len(idx) == top
    ids = {r["id"] for r in records["records"]}
    assert all(v in ids for v in idx.values())


def test_no_residual_markers(records):
    assert not _residuals(records), _residuals(records)[:5]


def test_reading_order_is_consistent(records):
    recs = records["records"]
    assert records["navigation"]["orderedIds"] == [r["id"] for r in recs]
    for i, r in enumerate(recs):
        assert r["prev"] == (recs[i - 1]["id"] if i else None)
        assert r["next"] == (recs[i + 1]["id"] if i + 1 < len(recs) else None)


def test_second_corpus_still_segments(rawd_records):
    """
    al-Rawd al-Mictar tags entries with `### $DIC_TOP$`, not `### |`. Configured
    with the wrong pattern it produced 86 records with markers left in the text;
    with the right one, 3,255 and none. The count is pinned in
    fixtures/rawd.yaml — its own file, because it is its own corpus.
    """
    import yaml
    from pathlib import Path

    pins = yaml.safe_load(
        (Path(__file__).parent / "fixtures" / "rawd.yaml").read_text(encoding="utf-8")
    )
    assert len(rawd_records["records"]) == pins["records"]["total"]
    assert not _residuals(rawd_records), _residuals(rawd_records)[:5]


# --- Muwatta': structural hierarchy and body-line openers -------------------
#
# Added at Phase 3. Both properties below were assumptions inside segment.py
# until this corpus was configured: that heading level must be guessed from a
# heading's wording, and that a numbered opener lives on the section line.


def _muwatta():
    import collections as _c, json
    from conftest import BUILD
    path = BUILD / "muwatta" / "records.json"
    if not path.exists():
        pytest.skip("muwatta records not present — run the pipeline first")
    return json.loads(path.read_text(encoding="utf-8"))["records"]


def test_muwatta_structural_levels_match_the_file():
    """61 `### |` and 702 `### ||` in the source. Lexical inference collapsed
    both into bab, because a kitab heading reads `1 - كتاب ...` and does not
    start with its own keyword."""
    recs = _muwatta()
    import collections
    layers = collections.Counter(r["layer"] for r in recs)
    assert layers["heading_kitab"] == 61
    assert layers["heading_bab"] == 702


def test_muwatta_openers_split_hadith_not_babs():
    """Reading the opener only on section lines produced exactly one matn
    record per bab (703) instead of one per hadith."""
    recs = _muwatta()
    matn = [r for r in recs if r["layer"] == "matn"]
    assert len(matn) > 1500
    numbered = [r for r in matn if r.get("number")]
    assert len(numbered) / len(matn) > 0.95


def test_muwatta_edition_numbering_is_gapless_per_kitab():
    """The invariant we can actually check without a network.

    An external witness (sunnah.com) numbers this work continuously and
    disagrees with us by 6 units at book 4 -- because it numbers a different
    printed edition, giving book 1 thirty-two hadith where this file gives
    thirty. A disagreement with sunnah.com is therefore not a bug.

    What we CAN assert is fidelity to this file: no printed number may be
    MISSING, because a gap means the opener parser dropped a hadith.

    We deliberately do NOT assert uniqueness. Measured: this edition repeats a
    number four times -- 13 and 48 in Kitab al-Hajj (13 three times over),
    49 in Kitab al-Jihad, and two in Kitab al-Buyu'. The printed number is
    therefore not a key even within one kitab, which is the strongest argument
    for carrying a separate synthetic address: `editionNumber` cannot address
    a record, and `displayNumber` must.
    """
    recs = _muwatta()
    cur, per = None, {}
    for r in recs:
        if r["layer"] == "heading_kitab":
            cur = r["id"]; per[cur] = []
        elif r["layer"] == "matn" and cur:
            if r.get("editionNumber"):
                per[cur].append(r["editionNumber"])
    checked = 0
    for kid, nums in per.items():
        if not nums:
            continue
        checked += 1
        missing = sorted(set(range(1, max(nums) + 1)) - set(nums))
        assert not missing, f"gap in {kid}: missing {missing[:10]}"
    assert checked >= 55


def test_muwatta_display_numbers_are_a_dense_sequence():
    """displayNumber addresses a record; it must be 1..n with no holes."""
    recs = _muwatta()
    seq = [r["displayNumber"] for r in recs if r["layer"] == "matn"]
    assert seq == list(range(1, len(seq) + 1))
