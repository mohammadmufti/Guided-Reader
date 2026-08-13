"""
The committed sunnah.com address maps hold their derivation's invariants.

pipeline/sunnah_numbers.py derives these from a pinned scrape and refuses to
write unless every pair matches the witness at textual identity and the
hand-confirmed anchors hold. That protects the WRITE. This protects the
FILES: a later hand edit, a bad merge, or a re-derivation against a moved
upstream must not be able to ship a map that quietly violates what the
derivation proved. Needs no cache and no network — the maps are committed.

The anchors repeated here are the ones confirmed against the live site:
`shamail` entry 306 is sunnah.com/shamail:317 (the correspondence CORPORA.md
records as checked by hand — the very number the naive idInBook link got
wrong, and the one a first draft of the derivation also got wrong, mapping it
to 319 before per-chapter alignment fixed it); `bulugh` entry 5 is
/bulugh/1/5 and entry 327 is /bulugh/2/151, both fetched and read during
derivation.
"""

import json
from pathlib import Path

import pytest

import corpus

DATA = corpus.ROOT / "corpora" / "data"


def _load(name):
    path = DATA / f"{name}_sunnah_links.json"
    if not path.exists():
        pytest.skip(f"{path.name} not present")
    return json.loads(path.read_text(encoding="utf-8"))


def test_shamail_map_invariants():
    doc = _load("shamail")
    assert doc["_provenance"]["commit"], "provenance must pin the source commit"
    e = doc["entries"]
    assert len(e) == 402
    flat = sorted(r for v in e.values() for r in v["refs"])
    assert flat == list(range(1, 418)), \
        "the 402 entries must tile sunnah.com's numbers 1..417 exactly once"
    assert sum(1 for v in e.values() if len(v["refs"]) > 1) == 15, \
        "the site merges exactly 15 entries"
    assert e["306"]["refs"] == [317], \
        "ANCHOR: entry 306 is sunnah.com/shamail:317, confirmed by hand"
    assert e["1"]["refs"] == [1] and e["402"]["refs"] == [417]
    assert e["5"]["refs"] == [5, 6], \
        "the first merged entry — one entry, two numbers — per CORPORA.md"


def test_bulugh_map_invariants():
    doc = _load("bulugh")
    assert doc["_provenance"]["commit"], "provenance must pin the source commit"
    e = doc["entries"]
    assert len(e) == 1767
    books = {}
    for v in e.values():
        books.setdefault(v["book"], []).append(v["pos"])
    assert sorted(books) == list(range(1, 17)), "16 site books, 1..16"
    for b, pos in books.items():
        assert len(pos) == len(set(pos)), \
            f"book {b}: a duplicated position would address two hadith with one URL"
    # Colon refs are partial ON THE SITE — five books — and must stay
    # display-only; a map that grew refs for every entry has been synthesised.
    with_refs = {v["book"] for v in e.values() if "refs" in v}
    assert with_refs == {1, 3, 6, 13, 14}, \
        f"colon refs exist in exactly five books on the site, got {sorted(with_refs)}"
    assert e["5"] == {"book": 1, "pos": 5, "refs": [5]}, \
        "ANCHOR: entry 5 is /bulugh/1/5 (= bulugh:5), read live during derivation"
    assert (e["327"]["book"], e["327"]["pos"]) == (2, 151), \
        "ANCHOR: entry 327 is /bulugh/2/151, read live during derivation"


def test_muwatta_map_invariants():
    doc = _load("muwatta")
    assert doc["_provenance"]["commit"], "provenance must pin the source commit"
    e = doc["entries"]
    # 1,860 of the witness's 1,985 entries carry Arabic; the 125 textless
    # slots hold their place in the chapter zip and get no map entry — an
    # index the binder can never stamp needs no address.
    assert len(e) == 1860
    books = {}
    for v in e.values():
        assert "refs" not in v, \
            "the site advertises no collection numbering for the Muwatta; " \
            "a map that grew refs has been synthesised"
        books.setdefault(v["book"], []).append(v["pos"])
    assert sorted(books) == list(range(1, 62)), "61 site books, 1..61"
    for b, pos in books.items():
        assert len(pos) == len(set(pos)), \
            f"book {b}: a duplicated position would address two hadith with one URL"
    assert e["1"] == {"book": 1, "pos": 1}, \
        "ANCHOR: entry 1 is /malik/1/1, read live during derivation"
