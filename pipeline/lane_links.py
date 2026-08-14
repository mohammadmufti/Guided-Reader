"""
Curated Lane links for the closed class — the words the automatic
resolution gets wrong for structural reasons, each measured before it was
written down.

The automatic path (build.py) is: analyser root -> root_variants ->
headword match by three key tiers. It is right for the open vocabulary
and wrong for a handful of function words and homographs, in three ways
that no general rule fixes without breaking something it gets right:

  * THE ANALYSER'S ROOT IS A HOMOGRAPH'S. The kunya أَبِي (my father /
    Abu ...) roots as ابي — the verb أَبَى, to refuse — and the reader of
    hadith 1 of al-Nawawi's Forty was shown إِبْيَةٌ, "disdain", for the
    Commander of the Faithful's kunya. Lane files أَبٌ in the ابو article
    (n116). Keyed by vocalised form, because أَبَى (he refused) is a real
    word in these texts and shares the bare rasm: the override must not
    touch it.

  * ROOT_VARIANTS' ORDER PICKS A DIFFERENT WORD'S ARTICLE. بن / ابن root
    as بني, which Lane does not hold; the variants try بنى (to build)
    before بنو (sons), both exist... only بنى exists first, so the
    reader of an isnad was shown بَنَاهُ, "he built it". Lane's اِبْنٌ is
    n3342 under بنو. Keyed by folded form: there is no reading of بن or
    ابن in these texts that is not the kinship word.

  * LANE CITES THE VERB WITH ITS OBJECT SUFFIX. The verb نَوَى (he
    intended — the word the first hadith of the Forty turns on) cannot
    match Lane's citation نَوَاهُ at any tier, and its bare rasm collides
    with نَوًى, date-stones, which is what the panel showed. Keyed by
    vocalised form: date-stones is also a real word (it appears in the
    Muwatta'), and نَوًى keeps its tanwin in the key.

  * LANE HAS NO ARTICLE AT ALL. The relative pronouns الذي family root as
    لذذ (!) or وصل by analyser whim; Lane holds no article for them
    anywhere — searched, not assumed — so the correct panel is NO Lane
    section, which None declares. A wrong article is worse than none;
    the reader of اللَّذَيْنِ was being shown لَذَّ, "it was delicious".

Every (root, nodeid) target is verified against the ingested Lane by
verify() at build time — an override pointing at nothing fails the build
rather than shipping an empty panel.
"""

from normalise import normalise, voc_key

# Vocalisation-sensitive: the bare rasm is shared with a different word
# that must keep its automatic resolution.
LANE_OVERRIDES_VOC: dict[str, tuple[str, str]] = {
    voc_key("أَبِي"): ("ابو", "n116"),   # أَبٌ — the kunya, genitive
    voc_key("أَبُو"): ("ابو", "n116"),   # nominative
    voc_key("أَبَا"): ("ابو", "n116"),   # accusative
    voc_key("نَوَى"): ("نوى", "n44208"),  # نَوَاهُ — he intended it
}

# Folded-form keyed: every reading of these in the corpora is the closed-
# class word. None means Lane has no article: no Lane section at all.
LANE_OVERRIDES_FOLDED: dict[str, tuple[str, str] | None] = {
    "بن": ("بنو", "n3342"),      # اِبْنٌ
    "ابن": ("بنو", "n3342"),
    # The relative pronouns. Lane's lexicon has no article for any of
    # them — the automatic path was reaching لَذَّ through the analyser's
    # root لذذ.
    "الذي": None,
    "التي": None,
    "الذين": None,
    "اللذين": None,
    "اللذان": None,
    "اللتان": None,
    "اللتين": None,
    "اللاتي": None,
    "اللواتي": None,
    "اللائي": None,
}


def lookup(vocalized: str | None, *fallbacks: str | None):
    """The override for a surface entry, or a miss.

    Returns (hit, target): hit False means no override speaks and the
    automatic resolution proceeds; target None (with hit True) means Lane
    holds nothing for this word and no linkage ships.
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
        # Accept either shape: the raw ingest (root -> {entries: [...]}) or
        # build.py's index (root -> [...]).
        if isinstance(entries, dict):
            entries = entries.get("entries")
        assert entries, f"lane_links: no Lane article for {root!r}"
        assert any(e["nodeid"] == nodeid for e in entries), \
            f"lane_links: {nodeid!r} is not an entry under {root!r}"
