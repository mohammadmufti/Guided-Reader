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


def test_adab_map_invariants():
    doc = _load("adab")
    e = doc["entries"]
    assert len(e) == 1326
    def num(r):
        import re
        return r if isinstance(r, int) else int(re.match(r"\d+", r).group())
    nums = sorted(num(r) for v in e.values() for r in v["refs"])
    assert sorted(set(nums)) == list(range(1, 1323)), \
        "adab numbers must cover 1..1322 gapless"
    from collections import Counter
    dups = {n for n, c in Counter(nums).items() if c > 1}
    assert dups == {270, 348, 1001, 1319}, \
        "the site's quirks are the double 270 and three letter splits — " \
        f"got {sorted(dups)}"
    assert e["1"]["refs"] == [1], "ANCHOR: entry 1 is sunnah.com/adab:1"


def test_riyad_map_invariants():
    doc = _load("riyad")
    e = doc["entries"]
    assert len(e) == 1896
    flat = sorted(r for v in e.values() for r in v["refs"] if isinstance(r, int))
    assert flat == list(range(1, 1897)), "riyad refs must tile 1..1896"
    # THE untangling this map exists for: the witness scrape appended the
    # site's first book last, so a link built on idInBook would be wrong for
    # every hadith in the collection.
    assert e["1"]["refs"] == [680], "witness entry 1 is the site's 680"
    assert e["1218"]["refs"] == [1], "the miscellany's first is witness 1218"


def test_muslim_map_invariants():
    doc = _load("muslim")
    e = doc["entries"]
    assert len(e) == 7459
    nolink = [k for k, v in e.items() if v.get("nolink")]
    assert len(nolink) == 83, \
        "the muqaddima's Introduction-style entries are declared no-links"
    import re
    def num(r):
        return r if isinstance(r, int) else int(re.match(r"\d+", r).group())
    nums = sorted({num(r) for v in e.values() for r in v.get("refs", [])})
    missing = set(range(1, nums[-1] + 1)) - set(nums)
    # The site's own numbering gaps, measured then pinned.
    assert nums[-1] == 3033 and missing == \
        {1698, 1824, 2483, 3007, 3008, 3009, 3010, 3011, 3012, 3013, 3014}
    # ANCHOR read live: muslim:8a is the Yahya b. Ya'mur qadar hadith, the
    # Book of Faith's first entry.
    first_faith = min(int(k) for k, v in e.items() if "refs" in v
                      and not v.get("nolink"))
    assert e[str(first_faith)]["refs"] == ["8a"]
