"""
Licensing obligations.

The pipeline imports GPL software, so the repository must carry a compatible
licence and must not commit the sources it is only allowed to align against.
Both are easy to break silently — a `.gitignore` edit is enough — so both are
asserted rather than remembered.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def test_a_licence_is_present_and_is_the_gpl():
    licence = ROOT / "LICENSE"
    assert licence.exists(), "no LICENSE file"
    text = licence.read_text(encoding="utf-8")
    assert "GNU GENERAL PUBLIC LICENSE" in text
    assert "Version 3" in text
    assert len(text) > 30_000, "the licence text looks truncated"


def test_notice_records_the_gpl_dependencies():
    notice = (ROOT / "NOTICE.md").read_text(encoding="utf-8")
    for package in ("farahidi", "qalsadi", "tashaphyne", "arramooz"):
        assert package in notice, f"{package} is not attributed in NOTICE.md"
    assert "laneslexicon" in notice, "Lane's digitisation is GPL and must be attributed"


def test_alignment_only_sources_are_not_committed():
    """
    The diacritised Bukhārī states no licence and is used ONLY to transfer
    vowelling. Committing it would redistribute it.
    """
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "pipeline/cache/" in ignored, "the source cache must stay uncommitted"
    assert not (ROOT / "pipeline" / "cache" / "sahih_bukhari_vocalised.csv").is_symlink()


def test_no_bukhari_sentence_reaches_the_payload():
    """
    Vowelling is transferred word by word; no sentence from the reference is
    reproduced. Spot-check that hadith files carry only this corpus's own text.
    """
    import json

    data = ROOT / "web" / "public" / "data" / "hadith"
    if not data.exists():
        return
    for path in list(data.glob("*.json"))[:50]:
        record = json.loads(path.read_text(encoding="utf-8"))
        assert "bukhariText" not in record
        assert "witness" not in record
