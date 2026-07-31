"""
The corrections layer.

Its value is that a reading fixed by hand stays fixed through every rebuild.
These tests check the mechanism works and, separately, that the two errors found
by reading are still right — the pipeline handles both now, so the corrections
file is empty, and it should stay empty only for as long as that remains true.
"""

import json
from pathlib import Path

import pytest
import yaml

PIPELINE = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def corrections_doc(corpus):
    """corrections/{corpus}.yaml, parsed. Absent file == empty file: an empty
    corrections layer is the documented steady state, not a failure."""
    path = PIPELINE / "corrections" / f"{corpus}.yaml"
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def test_file_parses_and_every_entry_gives_a_reason(corrections_doc):
    doc = corrections_doc
    for section in ("by_token", "by_form"):
        for entry in doc.get(section) or []:
            assert entry.get("note", "").strip(), f"{section} entry without a note: {entry}"
            assert entry.get("surface"), f"{section} entry without a surface: {entry}"
            if section == "by_token":
                assert "record" in entry and "token" in entry
            else:
                assert "search_key" in entry


def test_corrections_are_applied(bindings, corrections_doc):
    """Every correction in the file must actually appear in the output."""
    doc = corrections_doc
    for entry in doc.get("by_token") or []:
        rec = bindings.get(str(entry["record"]))
        assert rec, f"record {entry['record']} not in the build"
        got = rec["tokens"][int(entry["token"])]["surface"]
        assert got == entry["surface"], f"{entry['record']}#{entry['token']}: {got}"


def test_the_errors_found_by_reading_are_still_right(bindings):
    """
    Regression cover for the two errors a reader caught. Both are handled by the
    pipeline rather than by a correction, which is the better outcome — a rule
    fixes a class, a correction fixes one word. If either regresses, the fix
    belongs in corrections/tajrid.yaml until the rule is repaired.
    """
    # إنما is كافة ومكفوفة: the noun after it is مبتدأ مرفوع.
    for rec in bindings.values():
        toks = rec["tokens"]
        for i, t in enumerate(toks):
            if i and toks[i - 1]["raw"] in ("إنما", "وإنما") and t["raw"] == "الأعمال":
                assert t["surface"].endswith("ُ"), t["surface"]

    # `عن X بن Y` — بن agrees with a name governed by a preposition.
    wrong = [
        t["surface"]
        for rec in bindings.values()
        for i, t in enumerate(rec["tokens"])
        if t["raw"] == "بن" and i >= 2 and rec["tokens"][i - 2]["raw"] == "عن"
        and t["surface"] != "بْنِ"
    ]
    assert not wrong, f"{len(wrong)} openings not majrur"
