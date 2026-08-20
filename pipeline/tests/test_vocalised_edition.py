"""
Restoring a printed edition's harakāt onto records segmented from a stripped text.

The mechanism is general — OpenITI strips diacritics from every book checked so
far — so these test the module, and the corpus-specific figures are pinned
where the corpus is built.
"""
import json
import unicodedata
from pathlib import Path

import pytest

import vocalised_edition as VE

PIPELINE = Path(__file__).resolve().parents[1]
RECORDS = PIPELINE / "build" / "riyad" / "records.json"


def test_tatweel_is_not_a_letter():
    """The bug that caused five of six failures on the first run.

    U+0640 TATWEEL sits INSIDE the 0621–064A range and is decoration: the .bok
    writes بـ and هـ where the OpenITI text does not. Counting it as a
    consonant makes those records fail to locate."""
    assert not VE.is_letter("\u0640")
    assert VE.rasm("بـالغني") == VE.rasm("بالغني")
    assert VE.is_letter("\u0628") and VE.is_letter("\u064a")


def test_marks_are_stripped_by_category_not_by_list():
    """A hand-listed set of harakāt misses what it did not think of."""
    assert VE.strip_marks("الصَّلاةُ") == "الصلاة"
    assert VE.strip_marks("مُقَيَّدًا") == "مقيدا"


def test_restore_verifies_before_replacing():
    """THE GATE. Strip the marks from what is taken and it must reproduce what
    was already there; a doubtful substitute is worse than a bare one."""
    rows = [{"id": 1, "nass": "قَالَ رَسُولُ اللهِ صلى الله عليه وسلم كَلاماً طَيِّباً"}]
    good = [{"textRaw": "قال رسول الله صلى الله عليه وسلم كلاما طيبا"}]
    stats = VE.restore(good, rows)
    assert stats["restored"] == 1 and stats["verify_failed"] == 0
    assert "قَالَ" in good[0]["textRaw"]

    # a record whose rasm is NOT in the source is left alone, not approximated
    other = [{"textRaw": "هذا نص مختلف تماما لا يوجد في الكتاب المذكور أصلا"}]
    before = other[0]["textRaw"]
    stats = VE.restore(other, rows)
    assert stats["restored"] == 0 and stats["unmatched"] == 1
    assert other[0]["textRaw"] == before


def test_short_records_are_skipped_not_guessed():
    """A handful of letters matches somewhere regardless."""
    rows = [{"id": 1, "nass": "بَابٌ فِي الصِّدْقِ وَالأَمَانَةِ وَحُسْنِ الخُلُقِ"}]
    rec = [{"textRaw": "باب"}]
    stats = VE.restore(rec, rows)
    assert stats["skipped"] == 1 and rec[0]["textRaw"] == "باب"


def test_footnotes_and_furniture_are_excluded():
    """The .bok carries the editors' footnotes and printed page markers; the
    OpenITI text does not, so including them inserts text the record never had."""
    rows = [{"id": 1, "nass": "مَتْنُ الحَدِيثِ هُنَا (¬1) -[108]- وَتَمَامُهُ\r¬__________\r(¬1) حاشية المحقق"}]
    voc, skel, _ = VE.build_stream(rows)
    assert "حاشية" not in voc, "the footnote block leaked into the body"
    assert "108" not in voc and "¬" not in voc


@pytest.mark.skipif(not RECORDS.exists(), reason="riyad not segmented here")
def test_riyad_matn_carries_the_editions_harakat():
    doc = json.loads(RECORDS.read_text(encoding="utf-8"))
    recs = doc["records"] if isinstance(doc, dict) else doc
    matn = [r for r in recs if r.get("layer") == "matn"]
    marks = sum(1 for r in matn for c in r["textRaw"]
                if unicodedata.category(c).startswith("M"))
    letters = sum(1 for r in matn for c in r["textRaw"] if VE.is_letter(c))
    assert marks / letters > 0.40, "the vocalised edition did not take"
