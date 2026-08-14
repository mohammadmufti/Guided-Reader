"""
The curated residue of Lane linking — two words, after the systematic
resolution took the rest.

The general machinery in build.py answers the CLASSES the first audit
found: a closed-class word links by direct identity only (the relative
pronouns get no article because Lane wrote none, not because they are
listed here); candidate roots compete on headword-match tier rather than
first-existing (so an article that contains this word's own entry beats
one that merely exists); and Lane's suffixed verb citations are indexed
under their stripped form (so نَوَى finds نَوَاهُ and no longer collides
with date-stones). None of those words appears below.

What remains is two words whose PRODUCTION INPUTS are measured-deficient
in a way no resolution can see past:

  * أَبِي / أَبُو / أَبَا — the kunya. The workbook row carries no root and
    its lemma is the surface itself, so everything rests on the analyser,
    whose root for this rasm is the refuse-verb's; the right article
    (ابو, holding أَبٌ) is only reachable if ءبو appears among the
    analyser's alternatives, which is the analyser's choice, not ours.
    Keyed by vocalisation because أَبَى — he refused — is a real word in
    these texts sharing the bare rasm, and it must keep its automatic
    path (tested).

  * بن / ابن — the workbook's lemma for بن is بِن, a spelling no Lane
    article contains under any candidate root, so tier-scoring has
    nothing to score; and the ابن rows carry a workbook misanalysis
    (pos=verb, glossed "return, fem. pl.") that poisons both the pos gate
    and the lemma. Lane's اِبْنٌ is n3342 under بنو. Keyed by folded form
    because no reading of these in these texts is anything else.

Both entries are belt over the braces: where the analyser's data is good
the systematic path reaches the same article, and when the workbook rows
are corrected these lines should be deleted and the tests below them
will still hold. Every target is verified against the ingested Lane at
build time.
"""

from normalise import normalise, voc_key

# Vocalisation-sensitive: the bare rasm is shared with a different word
# that must keep its automatic resolution.
LANE_OVERRIDES_VOC: dict[str, tuple[str, str]] = {
    voc_key("أَبِي"): ("ابو", "n116"),   # أَبٌ — the kunya, genitive
    voc_key("أَبُو"): ("ابو", "n116"),   # nominative
    voc_key("أَبَا"): ("ابو", "n116"),   # accusative
}

# Folded-form keyed: every reading of these in the corpora is the closed-
# class word.
LANE_OVERRIDES_FOLDED: dict[str, tuple[str, str] | None] = {
    "بن": ("بنو", "n3342"),      # اِبْنٌ
    "ابن": ("بنو", "n3342"),
}


def lookup(vocalized: str | None, *fallbacks: str | None):
    """The override for a surface entry, or a miss.

    Returns (hit, target): hit False means no override speaks and the
    systematic resolution proceeds; target None (with hit True) would mean
    Lane holds nothing for this word — no current entry uses it, but the
    shape stays so a future one can.
    """
    if vocalized:
        t = LANE_OVERRIDES_VOC.get(voc_key(str(vocalized)))
        if t is not None:
            return True, t
    for form in (vocalized, *fallbacks):
        if form and normalise(str(form)) in LANE_OVERRIDES_FOLDED:
            return True, LANE_OVERRIDES_FOLDED[normalise(str(form))]
    return False, None


def verify(lane_by_root: dict) -> None:
    """Every override target must exist in the ingested Lane, checked at
    build time: a curated link pointing at nothing is a config typo, and
    it should fail loudly here rather than draw an empty panel."""
    targets = [t for t in LANE_OVERRIDES_VOC.values()]
    targets += [t for t in LANE_OVERRIDES_FOLDED.values() if t is not None]
    for root, nodeid in targets:
        entries = lane_by_root.get(root)
        if isinstance(entries, dict):
            entries = entries.get("entries")
        assert entries, f"lane_links: no Lane article for {root!r}"
        assert any(e["nodeid"] == nodeid for e in entries), \
            f"lane_links: {nodeid!r} is not an entry under {root!r}"
