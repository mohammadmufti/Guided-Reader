"""Lane resolution: the systematic paths (closed-class identity, tier-scored
candidate roots, suffixed verb citations) and the two-word curated residue.
Each case here is one the first audit found live, diagnosed to its cause."""
import json
from pathlib import Path

import pytest

import lane_links
from normalise import dediac, normalise, root_variants, voc_key

LANE = Path(__file__).resolve().parents[1] / "build" / "lane" / "entries.json"
pytestmark = pytest.mark.skipif(not LANE.exists(),
                                reason="Lane not ingested here")


@pytest.fixture(scope="module")
def lane():
    return json.loads(LANE.read_text())


@pytest.fixture(scope="module")
def hw(lane):
    """The three headword tiers exactly as build.py constructs them,
    including the suffixed-citation pass."""
    hw_voc, hw_exact, hw_folded = {}, {}, {}
    for take_headwords in (True, False):
        for root, payload in lane.items():
            for e in payload.get("entries", []):
                forms = ([e.get("headword")] if take_headwords
                         else (e.get("forms") or []))
                for form in forms:
                    if not form:
                        continue
                    hw_voc.setdefault((root, voc_key(str(form))), e["nodeid"])
                    hw_exact.setdefault((root, dediac(str(form))), e["nodeid"])
                    hw_folded.setdefault((root, normalise(form)), e["nodeid"])
    for root, payload in lane.items():
        for e in payload.get("entries", []):
            h = str(e.get("headword") or "")
            for suffix in ("هُ", "هَا", "ه", "ها"):
                if h.endswith(suffix) and len(h) > len(suffix) + 1:
                    stripped = h[: -len(suffix)]
                    variants = [stripped]
                    if stripped.endswith("ا"):
                        variants.append(stripped[:-1] + "ى")
                    if stripped.endswith("َا"):
                        variants.append(stripped[:-2] + "َى")
                    for v in variants:
                        hw_voc.setdefault((root, voc_key(v)), e["nodeid"])
                        hw_exact.setdefault((root, dediac(v)), e["nodeid"])
                        hw_folded.setdefault((root, normalise(v)), e["nodeid"])
                    break
    return hw_voc, hw_exact, hw_folded


def test_suffixed_citation_reaches_the_verb(hw):
    hw_voc, _, _ = hw
    # The verb the first hadith of the Forty turns on: نَوَى must find
    # Lane's citation نَوَاهُ at the vocalised tier...
    assert hw_voc[("نوى", voc_key("نَوَى"))] == "n44208"
    # ...while the date-stones noun, tanwin and all, keeps its own entry.
    assert hw_voc[("نوى", voc_key("نَوًى"))] == "n44210"


def test_tier_scoring_reaches_the_words_own_entry(hw, lane):
    hw_voc, hw_exact, hw_folded = hw
    # بن roots as بني, which Lane does not hold; the variants are بنى then
    # بنو. The production bug was not WHICH existed first — it was that the
    # old path took the first existing article and then matched nothing in
    # it (the workbook's lemma for بن is بِن, a spelling no article
    # contains), so the panel showed that article's first entry: بَنَاهُ,
    # "he built it". With the analyser's lemma اِبْن, BOTH variants hold
    # the word's own entry — Lane cross-lists اِبْنٌ under بنى and بنو —
    # and the tier scorer lands on a son article from either side.
    variants = [v for v in root_variants("بني") if v in ("بنى", "بنو")]
    assert variants == ["بنى", "بنو"], "the ordering the old rule fell on"
    by_id = {e["nodeid"]: e for r in lane.values() for e in r["entries"]}
    for root in ("بنى", "بنو"):
        node = hw_exact[(root, dediac("اِبْن"))]
        assert by_id[node]["headword"].startswith("اِبْن"), \
            f"{root}'s match for the lemma must be the son entry"


def test_closed_class_identity_only(lane):
    # الذي and family: no Lane article under any orthographic variant of
    # the lemma itself — the correct panel is no Lane section.
    for lemma in ("الذي", "التي", "الذين", "اللذين"):
        assert not any(v in lane for v in root_variants(normalise(lemma)))
    # But real particle articles survive the rule: في resolves to فى by
    # identity, and the article holds the particle itself.
    assert next(v for v in root_variants(normalise("في")) if v in lane) == "فى"
    assert any(e["headword"] == "فِى" for e in lane["فى"]["entries"])


def test_curated_residue_is_two_words_and_their_homographs_pass():
    assert lane_links.lookup("أَبِي") == (True, ("ابو", "n116"))
    assert lane_links.lookup("بِنْ", "بن") == (True, ("بنو", "n3342"))
    # The relative pronouns and نَوَى are NOT in the table any more — the
    # systematic paths carry them.
    assert lane_links.lookup("اللَّذَيْنِ") == (False, None)
    assert lane_links.lookup("نَوَى") == (False, None)
    # And the homographs the vocalisation keys protect:
    assert lane_links.lookup("أَبَى") == (False, None)   # he refused
    assert lane_links.lookup("نَوًى") == (False, None)   # date-stones


def test_every_target_exists_in_lane(lane):
    lane_links.verify(lane)
    by_id = {e["nodeid"]: e for r in lane.values() for e in r["entries"]}
    assert by_id["n116"]["headword"] == "أَبٌ"
    assert by_id["n3342"]["headword"] == "اِبْنٌ"


def test_stopword_net_with_real_roots_still_reaches_lane(hw):
    """qalsadi's `stopword` tag also catches real derivational words —
    وَأَعْلَى stranded 195 entries on CI when closed-class meant identity
    only. The refined rule lets a closed-class word take a scored root ON A
    HEADWORD HIT, and the elative's own lemma is right there in Lane."""
    hw_voc, hw_exact, hw_folded = hw
    hit = any(
        (v, key("أَعْلَى")) in index
        for index, key in ((hw_voc, voc_key), (hw_exact, dediac),
                           (hw_folded, normalise))
        for v in root_variants("علي")
    )
    assert hit, "أَعْلَى must be reachable under its root's variants"


def test_junk_letter_root_correctly_yields_nothing(hw, lane):
    """أَيْضًا's analyser root is the bare letter ض. Lane HOLDS a
    letter-article under ض — which is exactly why exists-only linking is
    forbidden for the closed class: that article holds no أَيْضًا at any
    tier, and unlinked is the correct panel."""
    hw_voc, hw_exact, hw_folded = hw
    assert "ض" in lane
    assert not any(
        (v, key("أَيْضًا")) in index
        for index, key in ((hw_voc, voc_key), (hw_exact, dediac),
                           (hw_folded, normalise))
        for v in root_variants("ض")
    )


def test_identity_existence_is_not_enough(hw, lane):
    """The second CI failure: يَا's spelling variant يأ IS a Lane article —
    of يَأْيَأَ, 'to call a falcon' — with no vocative inside it, and هو's
    variant هى exists without holding هُوَ. Lane wrote no article FOR
    these words; the closed-class rule links only where the word's own
    headword answers, so all of them stay honestly unlinked."""
    hw_voc, hw_exact, hw_folded = hw
    assert "يأ" in lane and "هى" in lane, "the trap articles exist"
    for probe, seed in (("يَا", "يا"), ("هُوَ", "هو"), ("هٰذِهِ", "هذه")):
        assert not any(
            (v, key(probe)) in index
            for index, key in ((hw_voc, voc_key), (hw_exact, dediac),
                               (hw_folded, normalise))
            for v in root_variants(seed)
        ), f"{probe} must match nothing under its identity variants"


def test_vocalised_pos_blindness_is_filled_from_the_bare_form():
    """qalsadi answers pos='all' — unknown — for هُوَ and أَيْضًا WITH their
    harakat, and knows both at once from the bare spelling. The retry FILLS
    ONLY: كُلَّمَا's vocalised parse returns a definite (if debatable)
    'verb', and نَوَى's bare rasm sits on the stopword-adjacent noun نواة —
    a definite answer must stand, or every vocalised verb whose rasm
    collides with a function word gets silently reclassified."""
    ql = pytest.importorskip("qalsadi.lemmatizer")
    lem = ql.Lemmatizer()
    from normalise import dediac as _dd

    def resolved_pos(form):
        got = lem.lemmatize(form, return_pos=True)
        if got and str(got[1]) in ("all", ""):
            bare = lem.lemmatize(_dd(form), return_pos=True)
            if bare and str(bare[1]) not in ("all", ""):
                got = bare
        return str(got[1]) if got else None

    assert resolved_pos("هُوَ") == "stopword"
    assert resolved_pos("أَيْضًا") == "stopword"
    assert resolved_pos("بِهَؤُلَاءِ") == "stopword"
    assert resolved_pos("كُلَّمَا") == "verb", "definite answers stand"
