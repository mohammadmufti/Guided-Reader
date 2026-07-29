"""
Segmentation, on both corpora.

The second corpus is the whole basis of the generalisation claim, and it is
exercised nowhere else. `segment.py` contains no Arabic string and no
corpus-specific regex; if that stops being true, this is what says so.
"""

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


def test_tajrid_record_counts(records):
    by_layer = {}
    for r in records["records"]:
        by_layer[r["layer"]] = by_layer.get(r["layer"], 0) + 1
    assert len(records["records"]) == 2_550
    assert by_layer["matn"] == 2_254
    assert by_layer["heading_kitab"] == 92
    assert by_layer["heading_bab"] == 115
    assert by_layer["zawaid"] == 88
    assert by_layer["frontmatter"] == 1


def test_every_display_number_resolves(records):
    """
    The spec expected ~13 gaps. There are none: 1202 shares an opener line with
    1201 and both resolve to that record.
    """
    numbers = sorted(n for r in records["records"] for n in r["numbersCovered"])
    assert numbers == list(range(1, 2_255))
    idx = records["navigation"]["numberIndex"]
    assert len(idx) == 2_254
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
    with the right one, 3,255 and none.
    """
    assert len(rawd_records["records"]) == 3_255
    assert not _residuals(rawd_records), _residuals(rawd_records)[:5]
