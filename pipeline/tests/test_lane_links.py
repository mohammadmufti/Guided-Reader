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
