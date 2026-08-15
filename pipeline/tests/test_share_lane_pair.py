"""The shared merge must not manufacture entries no build produced.

The chimera the CI invariant caught: al-Tajrid ships هُوَ closed and
unlinked (pos=particle, lane fields null); a minted corpus — whose
vocalised-form analysis got no pos back and legally took the open path —
ships the same word with the exists-only fallback article. The field-wise
gap-fill stitched one row's pos to the other row's lane_root: an
exists-only closed-class link neither corpus built."""
import json

import pytest

import share


def _corpus(tmp_path, name, entry):
    d = tmp_path / name / "lex"
    d.mkdir(parents=True)
    (d / "surface-000.json").write_text(
        json.dumps({"هو#aaaaaa": entry}, ensure_ascii=False), encoding="utf-8")
    return tmp_path / name


def test_lane_pair_travels_together_and_the_chimera_is_scrubbed(tmp_path):
    tajrid = _corpus(tmp_path, "tajrid", {
        "vocalized": "هُوَ", "unvocalized": "هو", "pos": "particle",
        "lane_root": None, "laneEntry": None,
    })
    minted = _corpus(tmp_path, "nawawi40", {
        "vocalized": "هُوَ", "unvocalized": "هو", "pos": None,
        "lane_root": "ه", "laneEntry": None,
    })
    entries, _, conflicts = share.collect([tajrid, minted])
    assert not conflicts
    e = entries["هو#aaaaaa"]
    assert e["pos"] == "particle", "pos gap-fill still works"
    # The stitched combination — pos=particle with an exists-only article —
    # must not survive the merge, in either corpus order.
    assert e["lane_root"] is None and e["laneEntry"] is None
    entries2, _, _ = share.collect([minted, tajrid])
    e2 = entries2["هو#aaaaaa"]
    assert e2["lane_root"] is None and e2["laneEntry"] is None


def test_same_root_entry_refinement_still_merges(tmp_path):
    """Two corpora agree on the article; one resolved the entry inside it.
    Taking the entry is a strict refinement, and the closed-class scrub
    must NOT touch the now-complete link."""
    a = _corpus(tmp_path, "a", {
        "vocalized": "قَدْ", "unvocalized": "قد", "pos": "particle",
        "lane_root": "قد", "laneEntry": None,
    })
    b = _corpus(tmp_path, "b", {
        "vocalized": "قَدْ", "unvocalized": "قد", "pos": "particle",
        "lane_root": "قد", "laneEntry": "n7777",
    })
    entries, _, _ = share.collect([a, b])
    e = entries["هو#aaaaaa"]
    assert e["lane_root"] == "قد" and e["laneEntry"] == "n7777"


def test_disagreeing_roots_do_not_mix(tmp_path):
    """Different articles from different corpora: the first stands whole;
    the second's entry must never attach to the first's root."""
    a = _corpus(tmp_path, "a", {
        "vocalized": "x", "unvocalized": "x", "pos": "noun",
        "lane_root": "كتب", "laneEntry": None,
    })
    b = _corpus(tmp_path, "b", {
        "vocalized": "x", "unvocalized": "x", "pos": "noun",
        "lane_root": "قرأ", "laneEntry": "n9999",
    })
    entries, _, _ = share.collect([a, b])
    e = entries["هو#aaaaaa"]
    assert e["lane_root"] == "كتب" and e["laneEntry"] is None
