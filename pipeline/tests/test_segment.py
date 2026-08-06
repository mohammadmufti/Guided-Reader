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


def test_muwatta_numbers_address_every_hadith_uniquely():
    """`number` must be an ADDRESS, not the printed number.

    It was the printed number, and this text restarts at 1 in every kitab. Sixty
    -one hadith called themselves 1, so `numberIndex` — built from
    `numbersCovered` — kept only the last of each and collapsed from 1,891
    entries to 255. Hadith 1 resolved to kitab 61, and 1,636 hadith could not be
    reached by number at all.
    """
    recs = _muwatta()
    matn = [r for r in recs if r["layer"] == "matn"]
    numbers = [r["number"] for r in matn]
    assert numbers == list(range(1, len(matn) + 1))
    covered = [n for r in matn for n in r["numbersCovered"]]
    assert len(set(covered)) == len(covered), "a number addresses two records"
    assert len(set(covered)) == len(matn)


def test_muwatta_keeps_the_printed_number_alongside():
    """The address is ours; the citation is the edition's. Both must survive.

    Not every record has a printed number: 59 matn records are Malik's own
    comment on the preceding hadith (`قال مالك: ...`) and the edition numbers
    none of them. Under the old scheme those had `number: None` and could not
    be linked to at all. They now have an address and no citation, which is the
    honest description of what they are.
    """
    recs = _muwatta()
    matn = [r for r in recs if r["layer"] == "matn"]
    printed = [r for r in matn if r.get("editionNumber")]
    assert len(printed) / len(matn) > 0.9
    # The two must genuinely differ, or the address is doing no work.
    assert any(r["editionNumber"] != r["number"] for r in printed)
    # And every record is addressable, numbered by the edition or not.
    assert all(r["number"] for r in matn)


def test_muwatta_chapter_indices_match_sunnah_com():
    """The kitab index is what the external link resolves with.

    Checked once against the sunnah.com-derived dataset (AhmedBaset/hadith-json,
    1,985 hadith, 61 chapters): our 61 kitab headings and their 61 chapters are
    in the same order with the same titles, 60 of 61 identical. The one
    difference is a naming variant in the same slot — ours كتاب الجامع, theirs
    كتاب المدينة — not a shift, confirmed by 43, 44, 46, 47 and 48 all agreeing
    around it.

    A change in the kitab count would silently point every link after it at the
    wrong book, so the count is pinned here.
    """
    recs = _muwatta()
    kitabs = [r for r in recs if r["layer"] == "heading_kitab"]
    assert len(kitabs) == 61
    idxs = [r["kitab"]["index"] for r in kitabs if r.get("kitab")]
    assert idxs == list(range(1, 62))


def test_persian_letterforms_are_folded_to_arabic():
    """A farsi yeh is a yeh, and must not break a word in half.

    U+06CC and U+06A9 sit outside RE_WORD's \\u0621-\\u064a range, so
    `لَیْسَ` — written with a farsi yeh in Shah Wali Allah's source — tokenised
    as `لَ` and `ْسَ`: two half-words, each separately hoverable and neither
    meaning anything. 47 farsi yeh and 21 farsi kaf in that text; none in any
    other source here.
    """
    import json
    from conftest import BUILD
    path = BUILD / "shahwaliullah40" / "records.json"
    if not path.exists():
        pytest.skip("shahwaliullah40 records not present")
    recs = json.loads(path.read_text(encoding="utf-8"))["records"]
    text = " ".join(r["textRaw"] for r in recs)
    for cp in ("\u06cc", "\u06a9", "\u06be", "\u06d2"):
        assert cp not in text, f"unfolded variant U+{ord(cp):04X} reached the payload"

    from tokenise import tokenise
    matn = [r for r in recs if r["layer"] == "matn"]
    _, toks = tokenise(matn[0]["textRaw"])
    # Three whole words, not five fragments.
    assert all(len(t["raw"]) > 1 for t in toks)
