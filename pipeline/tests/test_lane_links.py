"""The curated Lane links: the closed class the automatic resolution gets
wrong, each case measured before it was written down (lane_links.py)."""
import json
from pathlib import Path

import pytest

import lane_links
from normalise import voc_key

LANE = Path(__file__).resolve().parents[1] / "build" / "lane" / "entries.json"


def test_overrides_hit_exactly_the_reported_words():
    # The five words from al-Nawawi's Forty, hadith 1, that the audit found
    # or suspected — with the resolution each should have.
    assert lane_links.lookup("أَبِي") == (True, ("ابو", "n116"))      # أَبٌ
    assert lane_links.lookup("أَبُو") == (True, ("ابو", "n116"))
    assert lane_links.lookup("بِنْ", "بن") == (True, ("بنو", "n3342"))  # اِبْنٌ
    assert lane_links.lookup("اِبْن") == (True, ("بنو", "n3342"))
    assert lane_links.lookup("اللَّذَيْنِ") == (True, None)            # no article
    assert lane_links.lookup("الَّذِي") == (True, None)
    assert lane_links.lookup("نَوَى") == (True, ("نوى", "n44208"))     # نَوَاهُ


def test_homographs_keep_the_automatic_path():
    # The reason the أبي and نوى keys are vocalisation-sensitive: the same
    # rasm carries a different word that the table must NOT touch.
    assert lane_links.lookup("أَبَى") == (False, None)   # he refused
    assert lane_links.lookup("نَوًى") == (False, None)   # date-stones
    # And an open-vocabulary word passes straight through.
    assert lane_links.lookup("كِتَاب") == (False, None)


def test_voc_key_separates_what_the_table_relies_on():
    assert voc_key("أَبِي") != voc_key("أَبَى")
    assert voc_key("نَوَى") != voc_key("نَوًى")


@pytest.mark.skipif(not LANE.exists(), reason="Lane not ingested here")
def test_every_target_exists_in_lane():
    lane = json.loads(LANE.read_text())
    lane_links.verify(lane)
    # And the specific articles say what the overrides claim they say.
    by_id = {e["nodeid"]: e for r in lane.values() for e in r["entries"]}
    assert by_id["n116"]["headword"] == "أَبٌ"
    assert by_id["n3342"]["headword"] == "اِبْنٌ"
    assert by_id["n44208"]["headword"] == "نَوَاهُ"
