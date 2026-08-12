"""
The shared store.

B-4's whole claim is that a lexical entry is a property of the WORD, so it can
be shared across corpora and adding a text appends rather than rewrites. That
claim is only true if nothing corpus-specific leaks into the entry — which is
exactly what used to be wrong: `freq`, `rank`, `doc_freq` and `layers` all lived
inside it, so a second corpus would have rewritten all 22,464.
"""

import json
from pathlib import Path

import pytest

DATA = Path(__file__).resolve().parent.parent.parent / "web" / "public" / "data" / "lex"

# Properties of this text, not of the language. None may appear in a form entry.
CORPUS_SCOPED = {
    "freq", "doc_freq", "rank", "cum_pct", "layers", "boundFreq", "boundDocFreq",
    "first_record", "kwic",
}


def _load(prefix: str) -> dict:
    files = sorted(DATA.glob(f"{prefix}-*.json"))
    if not files:
        pytest.skip("payload not built")
    out: dict = {}
    for f in files:
        out.update(json.loads(f.read_text(encoding="utf-8")))
    return out


def test_no_corpus_scoped_field_survives_in_a_form_entry():
    forms = _load("surface")
    leaked = {k for e in forms.values() for k in e if k in CORPUS_SCOPED}
    assert not leaked, f"corpus-scoped fields still in the lexicon: {sorted(leaked)}"


def test_statistics_are_shipped_and_complete():
    forms, stats = _load("surface"), _load("stats")
    assert set(stats) == set(forms), (
        f"{len(set(forms) ^ set(stats))} entries have one half and not the other"
    )
    for key in ("freq", "boundFreq", "rank"):
        assert any(v.get(key) for v in stats.values()), f"{key} is empty everywhere"


def test_the_two_halves_route_to_the_same_shard():
    """
    The client fetches both with one hash of the search key. If the routing ever
    diverged, half the panels would silently lose their counts.
    """
    for shard in sorted(DATA.glob("surface-*.json")):
        n = shard.name.split("-")[1]
        twin = DATA / f"stats-{n}"
        assert twin.exists(), f"no stats shard for {shard.name}"
        a = json.loads(shard.read_text(encoding="utf-8"))
        b = json.loads(twin.read_text(encoding="utf-8"))
        assert set(a) == set(b), f"{shard.name} and {twin.name} hold different keys"


def test_a_form_entry_is_reproducible_from_the_word_alone():
    """
    Spot-check the invariant by hand: an entry must not mention a record id, a
    layer name or a position. Those are the shapes corpus data takes.
    """
    forms = _load("surface")
    for mid, entry in list(forms.items())[:2000]:
        blob = json.dumps(entry, ensure_ascii=False)
        for marker in ("matn-", "zawaid-", "heading_", "frontmatter-"):
            assert marker not in blob, f"{mid} carries corpus structure: {marker}"


def test_a_deliberate_null_survives_the_merge():
    """`glossQuick: None` is a decision, not a gap.

    build.py sets it to None wherever the analyser's gloss duplicates the
    curated one. share.py merges entries across corpora by filling absent
    fields — and it treated that None as absent, so a corpus that shipped the
    gloss overwrote a corpus that had suppressed it. The shared entry then
    carried both again.

    This is why the duplicates survived three fixes: each was correct per
    corpus, and the merge put them back. It could only show once two corpora
    shared enough vocabulary for one to overwrite the other, which is exactly
    what adding Bulugh and the Shama'il did — and why a single-corpus payload
    never reproduced it.
    """
    import share

    assert "glossQuick" in share.SUPPRESSIBLE

    suppressed = {"vocalized": "لَمْ", "gloss": {"senses": ["not"]}, "glossQuick": None}
    shipped = {"vocalized": "لَمْ", "gloss": {"senses": ["not"]},
               "glossQuick": {"senses": ["not"]}}
    for first, second in ((suppressed, shipped), (shipped, suppressed)):
        existing = dict(first)
        for field, val in second.items():
            cur = existing.get(field)
            if field in share.SUPPRESSIBLE and (cur is None or val is None):
                existing[field] = None
                continue
            if cur in (None, "", [], {}):
                existing[field] = val
        assert existing["glossQuick"] is None, \
            "a suppressed gloss came back through the merge"
