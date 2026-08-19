"""
Corpus isolation. Phase 1.

The bug this guards against was silent, which is why it survived: `bind.py` and
`lexicon.py` accepted `--corpus` and used it ONLY to choose an output
directory, while reading al-Tajrid's workbook and Sahih al-Bukhari as literals.
`python pipeline/lexicon.py --corpus rawd` therefore wrote al-Tajrid's lexicon
to `build/rawd/lexicon.json`, and `build.py` consumed it without complaint.

Nothing crashed. A geographical dictionary bound against a hadith collection
mostly falls to Tier 5, so the symptom was a failing coverage gate — which
reads as "the line grammar needs work", not "you are binding the wrong book".

These tests need no cache, no workbook and no network: they assert on
configuration resolution, which is where the mistake lived.
"""

import pytest

import corpus


CORPORA = sorted(p.stem for p in corpus.CORPORA.glob("*.yaml"))


def test_every_corpus_config_declares_a_matching_id():
    """A yaml whose `id` disagrees with its filename would send every derived
    path to the wrong corpus's directory."""
    for cid in CORPORA:
        cfg = corpus.load_config(cid)
        assert cfg["id"] == cid


def test_unknown_corpus_names_the_available_ones():
    with pytest.raises(corpus.ConfigError) as e:
        corpus.load_config("no-such-text")
    for cid in CORPORA:
        assert cid in str(e.value)


def test_missing_optional_source_returns_none_rather_than_another_corpus_file():
    """The heart of it.

    `rawd` declares no lexicon and no vocalisation reference. The old code
    answered both questions with al-Tajrid's files. The only acceptable answers
    now are None (optional) or a raised error (required) — never a path
    belonging to a different corpus.
    """
    cfg = corpus.load_config("rawd")
    assert corpus.source_path(cfg, "lexicon", required=False) is None
    assert corpus.source_path(cfg, "vocalisation_reference", required=False) is None


def test_missing_required_source_fails_loudly_and_names_the_corpus():
    cfg = corpus.load_config("rawd")
    with pytest.raises(corpus.ConfigError) as e:
        corpus.source_path(cfg, "lexicon", required=True)
    msg = str(e.value)
    assert "rawd" in msg
    assert "lexicon" in msg


def test_cache_directories_do_not_collide():
    """Sources used to land in one flat cache/ keyed only by a filename the
    yaml author chose. Two corpora picking the same name overwrote each
    other and the checksum guard then blamed the wrong text."""
    dirs = {cid: corpus.cache_dir(cid) for cid in CORPORA}
    assert len(set(dirs.values())) == len(dirs)


def test_source_filenames_are_unique_within_a_corpus():
    for cid in CORPORA:
        cfg = corpus.load_config(cid)
        names = [s["filename"] for s in (cfg.get("sources") or {}).values() if "filename" in s]
        assert len(names) == len(set(names)), f"{cid} declares a duplicate filename"


def test_only_corpora_with_expectations_are_gated():
    """A corpus with no `gates.min_witnessed_matn` must be reported, not
    silently passed against another corpus's threshold."""
    tajrid = corpus.load_config("tajrid")
    assert tajrid["gates"]["min_witnessed_matn"] == 90.0

    rawd = corpus.load_config("rawd")
    assert (rawd.get("gates") or {}).get("min_witnessed_matn") is None


def test_apparatus_patterns_are_per_corpus():
    """`(بخاري: N)` used to be stripped from every text regardless of config."""
    assert corpus.inline_strip_patterns(corpus.load_config("tajrid"))
    assert corpus.inline_strip_patterns(corpus.load_config("rawd")) == ()


# --- provenance of a minted corpus's morphology ----------------------------

def _muwatta_minted():
    import json
    path = corpus.ROOT / "build" / "muwatta" / "minted.json"
    if not path.exists():
        pytest.skip("muwatta bindings not present — run the pipeline first")
    return json.loads(path.read_text(encoding="utf-8"))


def test_minted_entries_always_carry_a_vowelling():
    """The one thing minting is FOR. Everything else may be absent."""
    minted = _muwatta_minted()
    assert minted
    assert all(e.get("vocalized") for e in minted.values())


def test_gloss_provenance_is_recorded_not_assumed():
    """A gloss borrowed from a sibling corpus must say so.

    It belongs to the word, not to the book -- but it was written for another
    text, and an interface that wants to disclose that has to be able to.
    """
    minted = _muwatta_minted()
    glossed = [e for e in minted.values() if e.get("gloss_msa")]
    assert glossed, "expected donor enrichment to have run"
    assert all(e.get("glossFrom") for e in glossed)


def test_donors_do_not_supply_readings_only_meanings():
    """The invariant that keeps enrichment from becoming contamination.

    Every minted entry must have arrived from THIS corpus's own witness.
    A donor may fill in what a word means; it may never introduce a reading
    the alignment did not independently produce, because that would let one
    book's vowelling settle another book's ambiguities.
    """
    minted = _muwatta_minted()
    assert all(e.get("fromWitness") for e in minted.values())


# --- the workbook is a source, not a dependency ----------------------------

def test_glossary_carries_meaning_and_refuses_statistics():
    """The store that replaces the workbook as a pipeline input.

    It may say what a word MEANS, because that is true of the word wherever it
    occurs. It must NOT carry frequency, rank or any other measurement over
    al-Tajrid, because a shared store holding one book's statistics would let
    that book rank another book's candidates -- the same contamination as
    sharing an inventory, arriving by a quieter route.
    """
    import glossary
    assert "gloss_msa" in glossary.CARRY
    assert "divergence" in glossary.CARRY
    for stat in ("freq", "rank", "pct", "cum_pct", "doc_freq", "first_record"):
        assert stat in glossary.REFUSE
        assert stat not in glossary.CARRY


def test_glossary_export_is_keyed_by_form_not_by_corpus():
    """`match_id` is stable_id(search_key, vocalized). If it ever depended on
    frequency, an entry would stop being corpus-independent and the whole
    sharing story would quietly become wrong."""
    import inspect
    from lexicon import stable_id
    sig = inspect.signature(stable_id)
    assert list(sig.parameters) == ["search_key", "vocalized"]


# --- the workbook is one text's exception, not the pipeline's shape ---------

def test_only_the_adapter_knows_about_spreadsheets():
    """No general module may parse the workbook.

    The workbook is a hand-built artefact for al-Tajrid alone, and it should
    keep being used for al-Tajrid -- it is that book's best evidence and holds
    21,028 curated glosses. But one text's exceptional input becomes every
    text's problem the moment a shared module knows a sheet name, so all of
    that lives in `workbook.py` and nowhere else.
    """
    import pathlib
    allowed = {"workbook.py", "glossary.py", "analyse.py", "lexicon.py", "gold.py",
               "bakeoff_camel.py"}
    offenders = []
    for path in sorted(corpus.ROOT.glob("*.py")):
        if path.name in allowed:
            continue
        src = path.read_text(encoding="utf-8")
        for marker in ("read_excel", 'sheet_name="Surface"', 'sheet_name="Review"'):
            if marker in src:
                offenders.append(f"{path.name}: {marker}")
    assert not offenders, f"workbook parsing leaked out of the adapter: {offenders}"


def test_lexicon_takes_rows_not_a_file():
    """`Lexicon` must not be able to tell where its inventory came from."""
    import inspect
    from bind import Lexicon
    params = list(inspect.signature(Lexicon.__init__).parameters)
    assert params == ["self", "curated", "review"]


def test_a_corpus_without_curation_needs_no_code():
    """The point of the isolation: adding a text touches config, not modules."""
    for cid in ("muwatta", "rawd"):
        cfg = corpus.load_config(cid)
        assert not (cfg.get("sources") or {}).get("lexicon")
        assert not (cfg.get("segmentation") or {}).get("curated_index_phantoms")


def test_shared_lexicon_carries_meaning_not_statistics():
    """`share.py` merges entries across corpora; it must not merge counts.

    Same rule as the glossary, enforced at a different layer: `freq`, `rank`
    and the rest describe a word IN ONE BOOK, and a shared store holding them
    would let one book's statistics rank another book's candidates.
    """
    import share
    src = (corpus.ROOT / "share.py").read_text(encoding="utf-8")
    assert "stats-" not in src.replace("stats-NNN.json", ""), \
        "share.py must not touch the per-corpus statistics shards"
    assert hasattr(share, "collect")


def test_share_refuses_to_merge_conflicting_identities():
    """If two corpora disagree on a form's identity, match_id has stopped
    identifying a reading and merging would silently pick one."""
    import share
    src = (corpus.ROOT / "share.py").read_text(encoding="utf-8")
    assert "REFUSING TO SHARE" in src
    for field in ("vocalized", "search_key", "unvocalized"):
        assert field in src


def test_exit_code_and_reported_gate_cannot_disagree():
    """`bind.py` must not print PASS and then exit non-zero.

    It did: the report used the per-corpus `gates.min_witnessed_matn` while the
    exit code recomputed its own hardcoded `>= 90` over Tiers 1 and 2 only. The
    Muwatta' reported PASS at 73.0% against its declared 68.0% and failed CI.

    Guarded structurally rather than by running a bind: the exit path must read
    the threshold from config and take its witnessed tiers from `tiers.py`.
    """
    src = (corpus.ROOT / "bind.py").read_text(encoding="utf-8")
    tail = src[src.rindex("def main("):]
    assert "min_witnessed_matn" in tail, "exit code must read the declared threshold"
    assert "t.witnessed" in tail, "exit code must use the tier table, not literals"
    assert "return 0 if t12 >= 90 else 1" not in src


def test_gloss_availability_is_read_from_the_build_not_the_payload():
    """`hasGlosses` drives the picker's 'vowelling only' warning.

    It was computed from the corpus's shipped surface shards — which `share.py`
    deletes once they are shared. Every already-shared corpus therefore reported
    `false`, and al-Tajrid, the one text with 21,028 curated glosses, was
    offered to the reader as vowelling-only.
    """
    src = (corpus.ROOT / "build.py").read_text(encoding="utf-8")
    fn = src[src.index("def _payload_has_glosses"):]
    fn = fn[:fn.index("\ndef ")]
    assert "lexicon.json" in fn, "must read the build output, not the payload"
    assert 'glob("surface-*.json")' not in fn


def test_corpus_independent_reference_data_is_shared():
    """Lane's Lexicon is the same book whichever text is being read.

    `classical-*` (headwords by root) and `lane-*` (the entries) were written
    per corpus and filled only from that corpus's own lexicon, so al-Tajrid
    shipped 1,829 entries and every other corpus shipped one empty shard. A
    Muwatta' word whose entry named a Lane root pointed at a file that was not
    there, and Lane silently appeared in one book out of three.
    """
    import share
    src = (corpus.ROOT / "share.py").read_text(encoding="utf-8")
    assert hasattr(share, "collect_named")
    # Every shared dictionary set, not a fixed pair: a new source that is
    # collected per corpus but never merged reproduces the original defect
    # for itself, one book at a time.
    assert '"classical", "lane", "lisan", "nihaya"' in src


def test_derived_lexicon_keeps_every_enriched_field():
    """The enrichment is pointless if the writer drops it.

    `derive_lexicon` had a fixed field list naming gloss, lemma, root and POS,
    so `lane_root`, `classical_keywords`, `domain` and the rest were enriched
    onto the entry and then thrown away on the way to lexicon.json. That is
    what removed Lane from every corpus without a workbook.
    """
    src = (corpus.ROOT / "bind.py").read_text(encoding="utf-8")
    fn = src[src.index("def derive_lexicon"):]
    fn = fn[:fn.index("\nTIER_NAMES")]
    assert "GLOSSARY_FIELDS" in fn


def test_every_corpus_can_describe_itself():
    """The info panel is data, not code.

    `AboutBook` renders whatever `about` the corpus declares, so a corpus
    without one silently has no info button — which is how the Muwatta' shipped
    for a while. Every corpus that reaches a reader must be able to say what it
    is and where its text came from.
    """
    for cid in CORPORA:
        cfg = corpus.load_config(cid)
        if corpus.is_lexical_source(cfg):
            continue          # apparatus, not a book a reader opens
        if cid == "rawd":
            continue          # a segmentation-only corpus
        about = cfg.get("about")
        assert about, f"{cid} has no `about` block"
        assert about.get("description"), f"{cid} describes nothing"
        assert len(about.get("sources") or []) >= 2, f"{cid} names too few sources"


def test_a_vowelled_source_is_evidence_on_its_own():
    """Tier 0 must be reachable without a workbook or a witness.

    The guard that refuses an evidence-less corpus was written before any
    source carried harakat, and refused Shah Wali Allah's Forty — 99.6%
    vowelled — on the grounds that it declared neither. It now measures the
    source instead of reading the config.
    """
    src = (corpus.ROOT / "bind.py").read_text(encoding="utf-8")
    assert "its source\\n" in src or "carries no harakat" in src
    cfg = corpus.load_config("shahwaliullah40")
    sources = cfg.get("sources") or {}
    assert "lexicon" not in sources and "vocalisation_reference" not in sources


def test_no_corpus_alters_the_letters_it_displays():
    """End to end: the rasm shown is the rasm fetched.

    Checked on the built bindings rather than on a helper, because the failure
    mode was not in any single function — it was that the surface came from
    whichever edition supplied the vowelling, and nothing compared it back to
    the source.
    """
    import json
    from normalise import dediac
    for cid in ("tajrid", "muwatta", "nawawi40", "shahwaliullah40"):
        path = corpus.ROOT / "build" / cid / "bindings.json"
        if not path.exists():
            continue
        bound = json.loads(path.read_text(encoding="utf-8"))
        bad = [
            (t["raw"], t["surface"])
            for rec in bound.values()
            for t in rec["tokens"]
            if dediac(t["raw"]) != dediac(t["surface"])
        ]
        assert not bad, f"{cid}: {len(bad)} tokens displayed different letters, e.g. {bad[:3]}"


def test_lane_headwords_beat_cited_forms():
    """An article's own headword must claim its key before a form it cites.

    Lane holds 48 entries under `رجل`, and six share the bare spelling. The
    article on the verb `رَجِلَ` cites the form `رَجُلَ`; the noun `رَجُلٌ` has
    exactly that headword. Indexed in one pass, the verb took the key, and the
    commonest noun in the corpus opened an article about walking on foot.

    Pinned structurally: the index must be built headword-pass first.
    """
    src = (corpus.ROOT / "build.py").read_text(encoding="utf-8")
    assert "for take_headwords in (True, False):" in src
    # And the candidates must run vocalised-lemma, then form, then bare lemma.
    # A bare candidate cannot use the vocalised tier, which is the tier that
    # separates entries sharing a spelling.
    assert 'for candidate in (_lv, e.get("vocalized"), e.get("lemma")):' in src
    assert 'lemmaVocalised' in src


def test_rajul_opens_the_noun_not_the_verb():
    """The case that found it, measured on the built payload."""
    import glob, json
    import pathlib
    shards = glob.glob(str(corpus.ROOT.parent / "web/public/data/lexicon/surface-*.json"))
    if not shards:
        pytest.skip("payload not built")
    entries = {}
    for f in shards:
        entries.update(json.loads(pathlib.Path(f).read_text(encoding="utf-8")))
    rajul = [e for e in entries.values()
             if e.get("vocalized") == "رَجُلٌ" and e.get("laneEntry")]
    if not rajul:
        pytest.skip("رَجُلٌ not in this payload")
    assert all(e["laneEntry"] == "n14929" for e in rajul), (
        f"expected the noun's article n14929, got {[e['laneEntry'] for e in rajul]}"
    )


def test_minted_entries_reach_lane():
    """A minted entry must carry the key its Lane article is found by.

    `build.py` OVERWRITES a derived-lexicon entry with the one in minted.json,
    nulling every field that file does not carry. minted.json had a fixed
    field list without `lane_root`, so an entry arrived at the trim with
    `lane_root: None` even though the derived lexicon held it — and no minted
    word ever reached Lane. Silent, because both files looked right on their
    own.
    """
    src = (corpus.ROOT / "bind.py").read_text(encoding="utf-8")
    writer = src[src.index('(out / "minted.json").write_text'):]
    writer = writer[:writer.index("encoding=\"utf-8\",")]
    for field in ("lane_root", "lemmaVocalised"):
        assert field in writer, f"minted.json drops {field}"


def test_root_variants_reach_lanes_own_spelling():
    """A root Lane holds under another spelling must still resolve.

    Lane collapses geminates (ردد -> رد), writes a final weak radical as alif
    maqsura (مني -> منى), and uses a bare alif where an analyser writes a hamza
    seat (ءمو -> امو). 4,408 entries claimed a root Lane does not hold AS
    SPELLED, and a classical shard was written for each — so the panel drew an
    empty root section rather than the root's first article.
    """
    from normalise import root_variants
    assert "رد" in root_variants("ردد")
    assert "منى" in root_variants("مني")
    assert "امو" in root_variants("ءمو")
    # An exact hit must always come first, so a variant is only a fallback.
    assert root_variants("كتم")[0] == "كتم"


def test_no_entry_ships_a_root_lane_cannot_resolve():
    """An unresolvable root is dropped, not shipped.

    Shipping it drew a root section with nothing in it, which reads as "Lane
    has nothing on this word" when Lane has an article under another spelling.
    """
    import glob, json, pathlib
    lane_path = corpus.ROOT / "build" / "lane" / "entries.json"
    shards = glob.glob(str(corpus.ROOT.parent / "web/public/data/lexicon/surface-*.json"))
    if not shards or not lane_path.exists():
        pytest.skip("payload or Lane build not present")
    lane = json.loads(lane_path.read_text(encoding="utf-8"))
    entries = {}
    for f in shards:
        entries.update(json.loads(pathlib.Path(f).read_text(encoding="utf-8")))
    bad = [e for e in entries.values()
           if e.get("lane_root") and e["lane_root"] not in lane]
    assert not bad, f"{len(bad)} entries ship a root Lane cannot resolve"


def test_quick_gloss_uses_the_stem_not_the_clitic_chain():
    """CAMeL's `gloss` decorates the stem with every clitic and case tag —
    `with;by_+_the+concealment;silence+[def.gen.]` for a word meaning
    concealment. `stemgloss` is the word."""
    src = (corpus.ROOT / "analyse.py").read_text(encoding="utf-8")
    assert 'a.get("stemgloss")' in src
    assert 'gloss_for' in src


def test_cache_rules_name_paths_that_exist():
    """`_headers` rules that match nothing are worse than none.

    The rules named `/data/index.json`, `/data/hadith/*` and `/data/lex/*`.
    None of those has existed since the payload was partitioned per corpus, so
    every rule matched nothing and the real files fell back to whatever the
    host sends.
    """
    src = (corpus.ROOT / "build.py").read_text(encoding="utf-8")
    block = src[src.index('"_headers"'):]
    block = block[:block.index("REPORTS.mkdir")]
    for path in ("/data/corpora.json", "/data/corpora/*/index.json",
                 "/data/corpora/*/hadith/*", "/data/lexicon/*"):
        assert path in block, f"no cache rule for {path}"
    assert '"/data/hadith/*' not in block, "a rule still names a path that moved"
    assert '"/data/lex/*' not in block


def test_shared_lexicon_urls_are_versioned():
    """An immutable URL that never changes is a cache that never updates.

    The shared shards deliberately carry no corpus buildId, so switching books
    does not re-download a lexicon the reader already holds. Without a version
    of their own, though, a reader who visited before a rebuild kept the old
    entries: the text updated and the word panel did not.
    """
    src = (corpus.ROOT.parent / "web/src/lib/lexicon.ts").read_text(encoding="utf-8")
    assert "lexVer(index)" in src
    assert "lexiconVersion" in src
    share = (corpus.ROOT / "share.py").read_text(encoding="utf-8")
    assert "lexiconVersion" in share and "hashlib" in share


def test_ci_segments_before_it_analyses():
    """`analyse.py` reads every corpus's records.json. CI ran it first.

    The stage was changed to analyse each corpus's own tokens so that a word in
    one book that al-Tajrid does not contain still gets a lemma and a root. In
    CI it ran BEFORE segmentation, so no records.json existed, the loop found
    nothing, and it analysed the workbook alone — the exact behaviour the
    change removed. Every word outside al-Tajrid's vocabulary shipped with no
    root, and the build was green throughout.

    It looked correct locally because segmentation is done by hand first.
    """
    wf = (corpus.ROOT.parent / ".github/workflows/deploy.yml").read_text(encoding="utf-8")
    seg = wf.index("Segment every corpus")
    ana = wf.index("Analyse morphology")
    assert seg < ana, "segmentation must come before the analyser in CI"


def test_the_analyser_refuses_to_run_blind():
    """A stage that silently does less than it claims is worse than one that
    stops. With no corpus records present, the workbook-only result looked
    like a normal run."""
    src = (corpus.ROOT / "analyse.py").read_text(encoding="utf-8")
    assert "NO CORPUS RECORDS FOUND" in src
    assert "seen_corpora == 0" in src


def test_every_corpus_witness_is_analysed():
    """A displayed surface must have been analysed, or it shows no root.

    A corpus without a workbook takes its whole inventory from its witness, and
    each token's SHOWN form is a vocalised witness reading. `mint_from_witness`
    looks the analysis up by that form. The stage read only al-Tajrid's
    witness, and restricted even that to keys the workbook already knew — right
    for al-Tajrid, whose inventory is the workbook, and wrong for every corpus
    whose inventory IS the witness.

    Nawawi showed "no root" for الصَّلَاةَ, عَظِيمٍ and يَسَّرَهُ. Their bare
    forms were analysed; the vocalised ones the reader actually sees were not.
    """
    src = (corpus.ROOT / "analyse.py").read_text(encoding="utf-8")
    assert "witness readings from" in src, \
        "analyse.py must read every corpus's witness, not only --corpus's"
    assert "WitnessIndex._read" in src, "must handle CSV and JSON witnesses alike"


def test_the_cross_reference_witness_does_not_vote_on_the_inventory():
    """It places an addition. It must not mint readings for other words.

    The numbered Bukhari is a DIFFERENT EDITION of the same book, carried so
    al-Diya's zawa'id can be located and linked. Minting its readings put them
    in the shared inventory, where they became rival candidates for matn tokens
    that previously had exactly one — Tier 1 on the matn fell from 97.2% to
    95.7%, a change to the whole corpus paid for a feature touching 88 records.

    A numbered row identifies that edition, so the guard reads off the row.
    """
    src = (corpus.ROOT / "bind.py").read_text(encoding="utf-8")
    assert "from_primary = witness_idx.numbers[row] is None" in src
    assert "if from_primary and (" in src


def test_the_additions_carry_the_editors_own_number():
    """al-Diya cites every one of his additions. Read it; do not guess it.

    He writes a bare `(4509)` after the report and comments after it, where
    al-Zabidi writes `(بخاري: N)` on the matn. All 88 additions carry one, and
    some carry two — `[238, 239]` where he quotes a pair.

    This is pinned because the alternative was tried and was wrong. Not seeing
    the number in the file, a retrieval was built to infer it from the text: it
    agreed with the editor on 1 of 76, and was systematically low, landing on a
    neighbouring hadith in the same chapter whose wording is near-identical.
    Containment measured 1.000 on those wrong answers, because a report on the
    same subject contains the same words. A confident measurement of the wrong
    quantity.
    """
    import json
    from conftest import BUILD
    path = BUILD / "tajrid" / "records.json"
    if not path.exists():
        pytest.skip("tajrid records not present")
    recs = json.loads(path.read_text(encoding="utf-8"))["records"]
    z = [r for r in recs if r["layer"] == "zawaid"]
    assert z, "no additions in this build"
    without = [r["id"] for r in z if not r.get("crossRefs")]
    assert not without, f"{len(without)} additions carry no reference, e.g. {without[:3]}"
    # And it must not be SHOWN as well as linked, or the reader sees it twice
    # and can click on it as a word. `textRaw` deliberately keeps the source
    # intact; the removal happens at tokenisation, so the payload is what to
    # check.
    import glob, pathlib, re as _re
    files = glob.glob(str(corpus.ROOT.parent /
                          "web/public/data/corpora/tajrid/hadith/zawaid-*.json"))
    if not files:
        return
    shown = []
    for f in files:
        toks = json.loads(pathlib.Path(f).read_text(encoding="utf-8")).get("tokens", [])
        text = "".join(t["raw"] + (t.get("punctuationAfter") or "") for t in toks)
        if _re.search(r"\(\d+\)", text):
            shown.append(f.split("/")[-1])
    assert not shown, f"{len(shown)} additions still show the number as text"

"""
Corpus isolation. Phase 1.

The bug this guards against was silent, which is why it survived: `bind.py` and
`lexicon.py` accepted `--corpus` and used it ONLY to choose an output
directory, while reading al-Tajrid's workbook and Sahih al-Bukhari as literals.
`python pipeline/lexicon.py --corpus rawd` therefore wrote al-Tajrid's lexicon
to `build/rawd/lexicon.json`, and `build.py` consumed it without complaint.

Nothing crashed. A geographical dictionary bound against a hadith collection
mostly falls to Tier 5, so the symptom was a failing coverage gate — which
reads as "the line grammar needs work", not "you are binding the wrong book".

These tests need no cache, no workbook and no network: they assert on
configuration resolution, which is where the mistake lived.
"""

import pytest

import corpus


CORPORA = sorted(p.stem for p in corpus.CORPORA.glob("*.yaml"))


def test_every_corpus_config_declares_a_matching_id():
    """A yaml whose `id` disagrees with its filename would send every derived
    path to the wrong corpus's directory."""
    for cid in CORPORA:
        cfg = corpus.load_config(cid)
        assert cfg["id"] == cid


def test_unknown_corpus_names_the_available_ones():
    with pytest.raises(corpus.ConfigError) as e:
        corpus.load_config("no-such-text")
    for cid in CORPORA:
        assert cid in str(e.value)


def test_missing_optional_source_returns_none_rather_than_another_corpus_file():
    """The heart of it.

    `rawd` declares no lexicon and no vocalisation reference. The old code
    answered both questions with al-Tajrid's files. The only acceptable answers
    now are None (optional) or a raised error (required) — never a path
    belonging to a different corpus.
    """
    cfg = corpus.load_config("rawd")
    assert corpus.source_path(cfg, "lexicon", required=False) is None
    assert corpus.source_path(cfg, "vocalisation_reference", required=False) is None


def test_missing_required_source_fails_loudly_and_names_the_corpus():
    cfg = corpus.load_config("rawd")
    with pytest.raises(corpus.ConfigError) as e:
        corpus.source_path(cfg, "lexicon", required=True)
    msg = str(e.value)
    assert "rawd" in msg
    assert "lexicon" in msg


def test_cache_directories_do_not_collide():
    """Sources used to land in one flat cache/ keyed only by a filename the
    yaml author chose. Two corpora picking the same name overwrote each
    other and the checksum guard then blamed the wrong text."""
    dirs = {cid: corpus.cache_dir(cid) for cid in CORPORA}
    assert len(set(dirs.values())) == len(dirs)


def test_source_filenames_are_unique_within_a_corpus():
    for cid in CORPORA:
        cfg = corpus.load_config(cid)
        names = [s["filename"] for s in (cfg.get("sources") or {}).values() if "filename" in s]
        assert len(names) == len(set(names)), f"{cid} declares a duplicate filename"


def test_only_corpora_with_expectations_are_gated():
    """A corpus with no `gates.min_witnessed_matn` must be reported, not
    silently passed against another corpus's threshold."""
    tajrid = corpus.load_config("tajrid")
    assert tajrid["gates"]["min_witnessed_matn"] == 90.0

    rawd = corpus.load_config("rawd")
    assert (rawd.get("gates") or {}).get("min_witnessed_matn") is None


def test_apparatus_patterns_are_per_corpus():
    """`(بخاري: N)` used to be stripped from every text regardless of config."""
    assert corpus.inline_strip_patterns(corpus.load_config("tajrid"))
    assert corpus.inline_strip_patterns(corpus.load_config("rawd")) == ()


# --- provenance of a minted corpus's morphology ----------------------------

def _muwatta_minted():
    import json
    path = corpus.ROOT / "build" / "muwatta" / "minted.json"
    if not path.exists():
        pytest.skip("muwatta bindings not present — run the pipeline first")
    return json.loads(path.read_text(encoding="utf-8"))


def test_minted_entries_always_carry_a_vowelling():
    """The one thing minting is FOR. Everything else may be absent."""
    minted = _muwatta_minted()
    assert minted
    assert all(e.get("vocalized") for e in minted.values())


def test_gloss_provenance_is_recorded_not_assumed():
    """A gloss borrowed from a sibling corpus must say so.

    It belongs to the word, not to the book -- but it was written for another
    text, and an interface that wants to disclose that has to be able to.
    """
    minted = _muwatta_minted()
    glossed = [e for e in minted.values() if e.get("gloss_msa")]
    assert glossed, "expected donor enrichment to have run"
    assert all(e.get("glossFrom") for e in glossed)


def test_donors_do_not_supply_readings_only_meanings():
    """The invariant that keeps enrichment from becoming contamination.

    Every minted entry must have arrived from THIS corpus's own witness.
    A donor may fill in what a word means; it may never introduce a reading
    the alignment did not independently produce, because that would let one
    book's vowelling settle another book's ambiguities.
    """
    minted = _muwatta_minted()
    assert all(e.get("fromWitness") for e in minted.values())


# --- the workbook is a source, not a dependency ----------------------------

def test_glossary_carries_meaning_and_refuses_statistics():
    """The store that replaces the workbook as a pipeline input.

    It may say what a word MEANS, because that is true of the word wherever it
    occurs. It must NOT carry frequency, rank or any other measurement over
    al-Tajrid, because a shared store holding one book's statistics would let
    that book rank another book's candidates -- the same contamination as
    sharing an inventory, arriving by a quieter route.
    """
    import glossary
    assert "gloss_msa" in glossary.CARRY
    assert "divergence" in glossary.CARRY
    for stat in ("freq", "rank", "pct", "cum_pct", "doc_freq", "first_record"):
        assert stat in glossary.REFUSE
        assert stat not in glossary.CARRY


def test_glossary_export_is_keyed_by_form_not_by_corpus():
    """`match_id` is stable_id(search_key, vocalized). If it ever depended on
    frequency, an entry would stop being corpus-independent and the whole
    sharing story would quietly become wrong."""
    import inspect
    from lexicon import stable_id
    sig = inspect.signature(stable_id)
    assert list(sig.parameters) == ["search_key", "vocalized"]


# --- the workbook is one text's exception, not the pipeline's shape ---------

def test_only_the_adapter_knows_about_spreadsheets():
    """No general module may parse the workbook.

    The workbook is a hand-built artefact for al-Tajrid alone, and it should
    keep being used for al-Tajrid -- it is that book's best evidence and holds
    21,028 curated glosses. But one text's exceptional input becomes every
    text's problem the moment a shared module knows a sheet name, so all of
    that lives in `workbook.py` and nowhere else.
    """
    import pathlib
    allowed = {"workbook.py", "glossary.py", "analyse.py", "lexicon.py", "gold.py",
               "bakeoff_camel.py"}
    offenders = []
    for path in sorted(corpus.ROOT.glob("*.py")):
        if path.name in allowed:
            continue
        src = path.read_text(encoding="utf-8")
        for marker in ("read_excel", 'sheet_name="Surface"', 'sheet_name="Review"'):
            if marker in src:
                offenders.append(f"{path.name}: {marker}")
    assert not offenders, f"workbook parsing leaked out of the adapter: {offenders}"


def test_lexicon_takes_rows_not_a_file():
    """`Lexicon` must not be able to tell where its inventory came from."""
    import inspect
    from bind import Lexicon
    params = list(inspect.signature(Lexicon.__init__).parameters)
    assert params == ["self", "curated", "review"]


def test_a_corpus_without_curation_needs_no_code():
    """The point of the isolation: adding a text touches config, not modules."""
    for cid in ("muwatta", "rawd"):
        cfg = corpus.load_config(cid)
        assert not (cfg.get("sources") or {}).get("lexicon")
        assert not (cfg.get("segmentation") or {}).get("curated_index_phantoms")


def test_shared_lexicon_carries_meaning_not_statistics():
    """`share.py` merges entries across corpora; it must not merge counts.

    Same rule as the glossary, enforced at a different layer: `freq`, `rank`
    and the rest describe a word IN ONE BOOK, and a shared store holding them
    would let one book's statistics rank another book's candidates.
    """
    import share
    src = (corpus.ROOT / "share.py").read_text(encoding="utf-8")
    assert "stats-" not in src.replace("stats-NNN.json", ""), \
        "share.py must not touch the per-corpus statistics shards"
    assert hasattr(share, "collect")


def test_share_refuses_to_merge_conflicting_identities():
    """If two corpora disagree on a form's identity, match_id has stopped
    identifying a reading and merging would silently pick one."""
    import share
    src = (corpus.ROOT / "share.py").read_text(encoding="utf-8")
    assert "REFUSING TO SHARE" in src
    for field in ("vocalized", "search_key", "unvocalized"):
        assert field in src


def test_exit_code_and_reported_gate_cannot_disagree():
    """`bind.py` must not print PASS and then exit non-zero.

    It did: the report used the per-corpus `gates.min_witnessed_matn` while the
    exit code recomputed its own hardcoded `>= 90` over Tiers 1 and 2 only. The
    Muwatta' reported PASS at 73.0% against its declared 68.0% and failed CI.

    Guarded structurally rather than by running a bind: the exit path must read
    the threshold from config and take its witnessed tiers from `tiers.py`.
    """
    src = (corpus.ROOT / "bind.py").read_text(encoding="utf-8")
    tail = src[src.rindex("def main("):]
    assert "min_witnessed_matn" in tail, "exit code must read the declared threshold"
    assert "t.witnessed" in tail, "exit code must use the tier table, not literals"
    assert "return 0 if t12 >= 90 else 1" not in src


def test_gloss_availability_is_read_from_the_build_not_the_payload():
    """`hasGlosses` drives the picker's 'vowelling only' warning.

    It was computed from the corpus's shipped surface shards — which `share.py`
    deletes once they are shared. Every already-shared corpus therefore reported
    `false`, and al-Tajrid, the one text with 21,028 curated glosses, was
    offered to the reader as vowelling-only.
    """
    src = (corpus.ROOT / "build.py").read_text(encoding="utf-8")
    fn = src[src.index("def _payload_has_glosses"):]
    fn = fn[:fn.index("\ndef ")]
    assert "lexicon.json" in fn, "must read the build output, not the payload"
    assert 'glob("surface-*.json")' not in fn


def test_corpus_independent_reference_data_is_shared():
    """Lane's Lexicon is the same book whichever text is being read.

    `classical-*` (headwords by root) and `lane-*` (the entries) were written
    per corpus and filled only from that corpus's own lexicon, so al-Tajrid
    shipped 1,829 entries and every other corpus shipped one empty shard. A
    Muwatta' word whose entry named a Lane root pointed at a file that was not
    there, and Lane silently appeared in one book out of three.
    """
    import share
    src = (corpus.ROOT / "share.py").read_text(encoding="utf-8")
    assert hasattr(share, "collect_named")
    # Every shared dictionary set, not a fixed pair: a new source that is
    # collected per corpus but never merged reproduces the original defect
    # for itself, one book at a time.
    assert '"classical", "lane", "lisan", "nihaya"' in src


def test_derived_lexicon_keeps_every_enriched_field():
    """The enrichment is pointless if the writer drops it.

    `derive_lexicon` had a fixed field list naming gloss, lemma, root and POS,
    so `lane_root`, `classical_keywords`, `domain` and the rest were enriched
    onto the entry and then thrown away on the way to lexicon.json. That is
    what removed Lane from every corpus without a workbook.
    """
    src = (corpus.ROOT / "bind.py").read_text(encoding="utf-8")
    fn = src[src.index("def derive_lexicon"):]
    fn = fn[:fn.index("\nTIER_NAMES")]
    assert "GLOSSARY_FIELDS" in fn


def test_every_corpus_can_describe_itself():
    """The info panel is data, not code.

    `AboutBook` renders whatever `about` the corpus declares, so a corpus
    without one silently has no info button — which is how the Muwatta' shipped
    for a while. Every corpus that reaches a reader must be able to say what it
    is and where its text came from.
    """
    for cid in CORPORA:
        cfg = corpus.load_config(cid)
        if corpus.is_lexical_source(cfg):
            continue          # apparatus, not a book a reader opens
        if cid == "rawd":
            continue          # a segmentation-only corpus
        about = cfg.get("about")
        assert about, f"{cid} has no `about` block"
        assert about.get("description"), f"{cid} describes nothing"
        assert len(about.get("sources") or []) >= 2, f"{cid} names too few sources"


def test_a_vowelled_source_is_evidence_on_its_own():
    """Tier 0 must be reachable without a workbook or a witness.

    The guard that refuses an evidence-less corpus was written before any
    source carried harakat, and refused Shah Wali Allah's Forty — 99.6%
    vowelled — on the grounds that it declared neither. It now measures the
    source instead of reading the config.
    """
    src = (corpus.ROOT / "bind.py").read_text(encoding="utf-8")
    assert "its source\\n" in src or "carries no harakat" in src
    cfg = corpus.load_config("shahwaliullah40")
    sources = cfg.get("sources") or {}
    assert "lexicon" not in sources and "vocalisation_reference" not in sources


def test_no_corpus_alters_the_letters_it_displays():
    """End to end: the rasm shown is the rasm fetched.

    Checked on the built bindings rather than on a helper, because the failure
    mode was not in any single function — it was that the surface came from
    whichever edition supplied the vowelling, and nothing compared it back to
    the source.
    """
    import json
    from normalise import dediac
    for cid in ("tajrid", "muwatta", "nawawi40", "shahwaliullah40"):
        path = corpus.ROOT / "build" / cid / "bindings.json"
        if not path.exists():
            continue
        bound = json.loads(path.read_text(encoding="utf-8"))
        bad = [
            (t["raw"], t["surface"])
            for rec in bound.values()
            for t in rec["tokens"]
            if dediac(t["raw"]) != dediac(t["surface"])
        ]
        assert not bad, f"{cid}: {len(bad)} tokens displayed different letters, e.g. {bad[:3]}"


def test_lane_headwords_beat_cited_forms():
    """An article's own headword must claim its key before a form it cites.

    Lane holds 48 entries under `رجل`, and six share the bare spelling. The
    article on the verb `رَجِلَ` cites the form `رَجُلَ`; the noun `رَجُلٌ` has
    exactly that headword. Indexed in one pass, the verb took the key, and the
    commonest noun in the corpus opened an article about walking on foot.

    Pinned structurally: the index must be built headword-pass first.
    """
    src = (corpus.ROOT / "build.py").read_text(encoding="utf-8")
    assert "for take_headwords in (True, False):" in src
    # And the candidates must run vocalised-lemma, then form, then bare lemma.
    # A bare candidate cannot use the vocalised tier, which is the tier that
    # separates entries sharing a spelling.
    assert 'for candidate in (_lv, e.get("vocalized"), e.get("lemma")):' in src
    assert 'lemmaVocalised' in src


def test_rajul_opens_the_noun_not_the_verb():
    """The case that found it, measured on the built payload."""
    import glob, json
    import pathlib
    shards = glob.glob(str(corpus.ROOT.parent / "web/public/data/lexicon/surface-*.json"))
    if not shards:
        pytest.skip("payload not built")
    entries = {}
    for f in shards:
        entries.update(json.loads(pathlib.Path(f).read_text(encoding="utf-8")))
    rajul = [e for e in entries.values()
             if e.get("vocalized") == "رَجُلٌ" and e.get("laneEntry")]
    if not rajul:
        pytest.skip("رَجُلٌ not in this payload")
    assert all(e["laneEntry"] == "n14929" for e in rajul), (
        f"expected the noun's article n14929, got {[e['laneEntry'] for e in rajul]}"
    )


def test_minted_entries_reach_lane():
    """A minted entry must carry the key its Lane article is found by.

    `build.py` OVERWRITES a derived-lexicon entry with the one in minted.json,
    nulling every field that file does not carry. minted.json had a fixed
    field list without `lane_root`, so an entry arrived at the trim with
    `lane_root: None` even though the derived lexicon held it — and no minted
    word ever reached Lane. Silent, because both files looked right on their
    own.
    """
    src = (corpus.ROOT / "bind.py").read_text(encoding="utf-8")
    writer = src[src.index('(out / "minted.json").write_text'):]
    writer = writer[:writer.index("encoding=\"utf-8\",")]
    for field in ("lane_root", "lemmaVocalised"):
        assert field in writer, f"minted.json drops {field}"


def test_every_resolvable_root_reaches_lane():
    """An invariant, not a percentage.

    The share of entries carrying a Lane root moves with corpus composition and
    with which corpora a given build produced — it read 76% on one machine and
    69% on CI for the same code. A threshold pinned to either number tests the
    build order, not the linkage.

    What must always hold: if an entry has a root, and that root resolves to
    Lane under any of Lane's own spellings, then the entry must carry
    `lane_root`. An entry whose root Lane genuinely lacks carries none, and
    the panel says nothing rather than drawing an empty section.
    """
    import glob, json, pathlib as _p
    from normalise import root_variants
    lane_path = corpus.ROOT / "build" / "lane" / "entries.json"
    shards = glob.glob(str(corpus.ROOT.parent / "web/public/data/lexicon/surface-*.json"))
    if not shards or not lane_path.exists():
        pytest.skip("payload or Lane build not present")
    lane = json.loads(lane_path.read_text(encoding="utf-8"))
    entries = {}
    for f in shards:
        entries.update(json.loads(_p.Path(f).read_text(encoding="utf-8")))

    from build import CLOSED_CLASS_POS
    from normalise import normalise as _norm

    # The exists => linked claim holds for the OPEN vocabulary. A
    # closed-class word (pos-tagged; qalsadi's `stopword` net also catches
    # real derivational words) links by identity or by a headword HIT, and
    # an analyser root whose article merely EXISTS is precisely what it
    # must refuse: أَيْضًا's analyser root is the bare letter ض, whose
    # letter-article Lane holds and which holds no أَيْضًا — unlinked is
    # the correct panel there, where the old rule would have drawn the
    # letter's article.
    missed = [
        e for e in entries.values()
        if e.get("root") and not e.get("lane_root")
        and e.get("pos") not in CLOSED_CLASS_POS
        and any(v in lane for v in root_variants(str(e["root"])))
    ]
    assert not missed, (
        f"{len(missed)} entries have a root Lane holds but carry no lane_root, "
        f"e.g. {[(x.get('vocalized'), x.get('root')) for x in missed[:3]]}"
    )

    # And the closed class's own invariant, one clause, from shipped
    # fields alone: a linked closed-class entry HAS a laneEntry. The first
    # draft of this check exempted identity-derived roots, and CI promptly
    # showed why existence is no better through identity than through a
    # guessed root: يَا's spelling variant يأ IS a Lane article — of
    # يَأْيَأَ, "to call a falcon" — holding no vocative, and thirty
    # pronouns shipped falcon-and-letter articles with nothing inside
    # them. An article that does not contain the word is not the word's
    # article, whichever path found it.
    bad_closed = [
        e for e in entries.values()
        if e.get("pos") in CLOSED_CLASS_POS and e.get("lane_root")
        and not e.get("laneEntry")
    ]
    assert not bad_closed, (
        f"{len(bad_closed)} closed-class entries link by mere existence, "
        f"e.g. {[(x.get('vocalized'), x.get('lane_root')) for x in bad_closed[:3]]}"
    )

def test_root_variants_reach_lanes_own_spelling():
    """A root Lane holds under another spelling must still resolve.

    Lane collapses geminates (ردد -> رد), writes a final weak radical as alif
    maqsura (مني -> منى), and uses a bare alif where an analyser writes a hamza
    seat (ءمو -> امو). 4,408 entries claimed a root Lane does not hold AS
    SPELLED, and a classical shard was written for each — so the panel drew an
    empty root section rather than the root's first article.
    """
    from normalise import root_variants
    assert "رد" in root_variants("ردد")
    assert "منى" in root_variants("مني")
    assert "امو" in root_variants("ءمو")
    # An exact hit must always come first, so a variant is only a fallback.
    assert root_variants("كتم")[0] == "كتم"


def test_no_entry_ships_a_root_lane_cannot_resolve():
    """An unresolvable root is dropped, not shipped.

    Shipping it drew a root section with nothing in it, which reads as "Lane
    has nothing on this word" when Lane has an article under another spelling.
    """
    import glob, json, pathlib
    lane_path = corpus.ROOT / "build" / "lane" / "entries.json"
    shards = glob.glob(str(corpus.ROOT.parent / "web/public/data/lexicon/surface-*.json"))
    if not shards or not lane_path.exists():
        pytest.skip("payload or Lane build not present")
    lane = json.loads(lane_path.read_text(encoding="utf-8"))
    entries = {}
    for f in shards:
        entries.update(json.loads(pathlib.Path(f).read_text(encoding="utf-8")))
    bad = [e for e in entries.values()
           if e.get("lane_root") and e["lane_root"] not in lane]
    assert not bad, f"{len(bad)} entries ship a root Lane cannot resolve"


def test_quick_gloss_uses_the_stem_not_the_clitic_chain():
    """CAMeL's `gloss` decorates the stem with every clitic and case tag —
    `with;by_+_the+concealment;silence+[def.gen.]` for a word meaning
    concealment. `stemgloss` is the word."""
    src = (corpus.ROOT / "analyse.py").read_text(encoding="utf-8")
    assert 'a.get("stemgloss")' in src
    assert 'gloss_for' in src


def test_cache_rules_name_paths_that_exist():
    """`_headers` rules that match nothing are worse than none.

    The rules named `/data/index.json`, `/data/hadith/*` and `/data/lex/*`.
    None of those has existed since the payload was partitioned per corpus, so
    every rule matched nothing and the real files fell back to whatever the
    host sends.
    """
    src = (corpus.ROOT / "build.py").read_text(encoding="utf-8")
    block = src[src.index('"_headers"'):]
    block = block[:block.index("REPORTS.mkdir")]
    for path in ("/data/corpora.json", "/data/corpora/*/index.json",
                 "/data/corpora/*/hadith/*", "/data/lexicon/*"):
        assert path in block, f"no cache rule for {path}"
    assert '"/data/hadith/*' not in block, "a rule still names a path that moved"
    assert '"/data/lex/*' not in block


def test_shared_lexicon_urls_are_versioned():
    """An immutable URL that never changes is a cache that never updates.

    The shared shards deliberately carry no corpus buildId, so switching books
    does not re-download a lexicon the reader already holds. Without a version
    of their own, though, a reader who visited before a rebuild kept the old
    entries: the text updated and the word panel did not.
    """
    src = (corpus.ROOT.parent / "web/src/lib/lexicon.ts").read_text(encoding="utf-8")
    assert "lexVer(index)" in src
    assert "lexiconVersion" in src
    share = (corpus.ROOT / "share.py").read_text(encoding="utf-8")
    assert "lexiconVersion" in share and "hashlib" in share


def test_ci_segments_before_it_analyses():
    """`analyse.py` reads every corpus's records.json. CI ran it first.

    The stage was changed to analyse each corpus's own tokens so that a word in
    one book that al-Tajrid does not contain still gets a lemma and a root. In
    CI it ran BEFORE segmentation, so no records.json existed, the loop found
    nothing, and it analysed the workbook alone — the exact behaviour the
    change removed. Every word outside al-Tajrid's vocabulary shipped with no
    root, and the build was green throughout.

    It looked correct locally because segmentation is done by hand first.
    """
    wf = (corpus.ROOT.parent / ".github/workflows/deploy.yml").read_text(encoding="utf-8")
    seg = wf.index("Segment every corpus")
    ana = wf.index("Analyse morphology")
    assert seg < ana, "segmentation must come before the analyser in CI"


def test_the_analyser_refuses_to_run_blind():
    """A stage that silently does less than it claims is worse than one that
    stops. With no corpus records present, the workbook-only result looked
    like a normal run."""
    src = (corpus.ROOT / "analyse.py").read_text(encoding="utf-8")
    assert "NO CORPUS RECORDS FOUND" in src
    assert "seen_corpora == 0" in src


def test_every_corpus_witness_is_analysed():
    """A displayed surface must have been analysed, or it shows no root.

    A corpus without a workbook takes its whole inventory from its witness, and
    each token's SHOWN form is a vocalised witness reading. `mint_from_witness`
    looks the analysis up by that form. The stage read only al-Tajrid's
    witness, and restricted even that to keys the workbook already knew — right
    for al-Tajrid, whose inventory is the workbook, and wrong for every corpus
    whose inventory IS the witness.

    Nawawi showed "no root" for الصَّلَاةَ, عَظِيمٍ and يَسَّرَهُ. Their bare
    forms were analysed; the vocalised ones the reader actually sees were not.
    """
    src = (corpus.ROOT / "analyse.py").read_text(encoding="utf-8")
    assert "witness readings from" in src, \
        "analyse.py must read every corpus's witness, not only --corpus's"
    assert "WitnessIndex._read" in src, "must handle CSV and JSON witnesses alike"


def test_the_cross_reference_witness_does_not_vote_on_the_inventory():
    """It places an addition. It must not mint readings for other words.

    The numbered Bukhari is a DIFFERENT EDITION of the same book, carried so
    al-Diya's zawa'id can be located and linked. Minting its readings put them
    in the shared inventory, where they became rival candidates for matn tokens
    that previously had exactly one — Tier 1 on the matn fell from 97.2% to
    95.7%, a change to the whole corpus paid for a feature touching 88 records.

    A numbered row identifies that edition, so the guard reads off the row.
    """
    src = (corpus.ROOT / "bind.py").read_text(encoding="utf-8")
    assert "from_primary = witness_idx.numbers[row] is None" in src
    assert "if from_primary and (" in src




def test_bulugh_and_shamail_link_only_through_the_address_map():
    """The per-hadith link exists again, and only via the verified map.

    The first version of this test asserted the OPPOSITE — that these two
    corpora must not link per hadith at all — because the link had been built
    from the witness's `idInBook` on the assumption that it is the number in
    a sunnah.com URL. It is not: the site merges entries, so
    sunnah.com/shamail:317 serves the hadith the dataset calls 306, and the
    step from row to URL could not be verified from that data alone.

    It can now. pipeline/sunnah_numbers.py derives the site's own addressing
    from a second scrape that kept the reference tables, refuses to write
    unless every entry matches the witness at textual identity and the
    hand-confirmed anchors hold, and tests/test_sunnah_links.py holds the
    committed maps to the same invariants. So the configuration must link —
    and must link THROUGH the map, never by shipping a witness index as if
    it were the site's number.
    """
    for cid, tmpl in (("bulugh", "bulugh/{book}/{pos}"),
                      ("shamail", "shamail:{n}"),
                      ("muwatta", "malik/{book}/{pos}"),
                      ("adab", "adab:{n}"),
                      ("riyad", "riyadussalihin:{n}"),
                      ("mukhtasar", "muslim:{n}")):
        cfg = corpus.load_config(cid)
        rl = (cfg.get("segmentation") or {}).get("record_link") or {}
        assert rl, f"{cid} has a verified address map and must link per hadith"
        assert rl.get("number_from_witness") and rl.get("link_map"), \
            f"{cid} must resolve its link from the aligned witness via the map"
        assert rl.get("ref_template") == tmpl, \
            f"{cid}: the address form was measured on the live site — " \
            f"shamail has a complete colon numbering, Bulugh has only paths"
        assert "{ref}" in rl.get("url", ""), \
            f"{cid}: the URL must be built from the map's address, not a number"
        assert (corpus.ROOT / rl["link_map"]).exists()


def test_map_linked_payloads_carry_site_addresses_not_witness_indices():
    """The shipped files carry the site's own address, and the anchors hold.

    Payload-level, because this is where the original bug lived: everything
    upstream was sound — the alignment, the coverage, the numbers — and the
    payload still linked wrong, because the number it shipped belonged to the
    wrong namespace. The anchor is the same one every layer of this feature
    is pinned to: this edition's Shama'il 319 is the witness's entry 306 is
    sunnah.com/shamail:317.
    """
    import glob, json, pathlib
    docs = {}
    for cid in ("bulugh", "shamail", "muwatta", "adab", "riyad",
                "mukhtasar"):
        fs = glob.glob(str(corpus.ROOT.parent /
                           f"web/public/data/corpora/{cid}/hadith/matn-*.json"))
        docs[cid] = [json.loads(pathlib.Path(f).read_text(encoding="utf-8"))
                     for f in fs]
        if not docs[cid]:
            pytest.skip(f"{cid} payload not built")
    sh = {d["number"]: d for d in docs["shamail"] if d.get("number")}
    assert sh[319].get("recordLinkRef") == "shamail:317", \
        "ANCHOR: this edition's 319 is sunnah.com/shamail:317"
    assert sh[319].get("recordLinkNumber") == 317
    bu = {d["number"]: d for d in docs["bulugh"] if d.get("number")}
    assert bu[5].get("recordLinkRef") == "bulugh/1/5", \
        "ANCHOR: read live during derivation"
    mu = {d["number"]: d for d in docs["muwatta"] if d.get("number")}
    assert mu[1].get("recordLinkRef") == "malik/1/1", \
        "ANCHOR: /malik/1/1 read live — the page that proved per-hadith " \
        "addressing exists for this text at all"
    ad = {d["number"]: d for d in docs["adab"] if d.get("number")}
    assert ad[1].get("recordLinkRef") == "adab:1", "ANCHOR: read live"
    mk = [d for d in docs["mukhtasar"] if d.get("recordLinkRef")]
    # A lettered address never fakes a numeric suffix — muslim:1662a and
    # muslim:1662b are different hadith — and a plain one always shows its
    # number. Both shapes must exist.
    lettered = [d for d in mk
                if any(c.isalpha() for c in d["recordLinkRef"].split(":")[1])]
    plain = [d for d in mk if d not in lettered]
    assert lettered and plain
    assert all(d.get("recordLinkNumber") is None for d in lettered)
    assert all(isinstance(d.get("recordLinkNumber"), int) for d in plain)
    assert not any("None" in d["recordLinkRef"] for d in mk)
    ri = {d["number"]: d for d in docs["riyad"] if d.get("number")}
    assert ri[1].get("recordLinkRef") == "riyadussalihin:1", \
        "the miscellany untangling, end to end: our 1 aligns to witness " \
        "entry 1218 and links the site's 1 — raw idInBook would say 1218"
    assert ri[680].get("recordLinkRef") == "riyadussalihin:680"
    # Coverage floor: the binder places nearly every record (99% for Bulugh
    # and the Shama'il, 94% for the Muwatta, whose number comes from a second
    # retrieval over the numbered rows and meets more near-identical short
    # reports); a witness or map regression that silently unlinks a swath
    # must fail. Floors sit below the measurements to catch regression, not
    # to restate them.
    # Floors differ for measured reasons. Riyad's bare-rasm witness (2.4%
    # vowelled) makes short-hadith retrieval noisier. The Mukhtasar's is
    # lowest of all: an abridgement against a collection that repeats its
    # reports leaves ~24% of records with no row the reading order can
    # vouch for, and those stay honestly unlinked.
    for cid, floor in (("bulugh", 0.95), ("shamail", 0.95), ("muwatta", 0.90),
                       ("adab", 0.95), ("riyad", 0.88), ("mukhtasar", 0.70)):
        if cid not in docs:
            continue
        matn = [d for d in docs[cid]
                if d.get("layer") == "matn" and d.get("number")]
        linked = [d for d in matn if d.get("recordLinkRef")]
        assert len(linked) / len(matn) >= floor, \
            f"{cid}: only {len(linked)} of {len(matn)} numbered matn link"
        # And an UNNUMBERED record never links: a fragment or a bab's verse
        # block is not a hadith, whatever its words overlap.
        assert not [d for d in docs[cid]
                    if not d.get("number") and d.get("recordLinkRef")], \
            f"{cid}: an unnumbered record claims a per-hadith page"
        # And a linked record never ships a bare witness index: every ref the
        # map produces has the collection's shape.
        shape = {"bulugh": "bulugh/", "shamail": "shamail:",
                 "muwatta": "malik/", "adab": "adab:",
                 "riyad": "riyadussalihin:",
                 "mukhtasar": "muslim:"}[cid]
        assert all(d["recordLinkRef"].startswith(shape) for d in linked)
        # Layers the config excludes carry nothing.
        others = [d for d in docs[cid] if d.get("layer") != "matn"]
        assert not [d for d in others
                    if d.get("recordLinkRef") or d.get("recordLinkNumber")]


def test_a_chapter_link_is_matched_by_title_not_position():
    """Two editions do not always divide a book into the same chapters.

    Bulugh's ninth kitab is كتاب الطلاق, which sunnah.com does not carry as a
    chapter of its own. A positional map is therefore off by one from there
    on, and every later link lands in the wrong book. Matching by title maps
    the 16 that correspond and leaves الطلاق unlinked.

    Position is a fallback, and only where both texts have the same number of
    chapters in the same order — the Shama'il's 57 against 57, where a handful
    are titled differently without disagreeing about which chapter they are.
    """
    import glob, json, pathlib
    src = (corpus.ROOT / "build.py").read_text(encoding="utf-8")
    assert "_by_title" in src and "len(_their) == _n_ours" in src

    docs = [json.loads(pathlib.Path(f).read_text(encoding="utf-8"))
            for f in glob.glob(str(corpus.ROOT.parent /
                                   "web/public/data/corpora/bulugh/hadith/matn-*.json"))]
    if not docs:
        pytest.skip("bulugh payload not built")
    # The chapter with no counterpart must carry no link.
    talaq = [d for d in docs if (d.get("kitab") or {}).get("titleAr", "").strip() == "كتاب الطلاق"]
    assert talaq, "كتاب الطلاق not found — has the text changed?"
    assert all(d.get("chapterLinkNumber") is None for d in talaq), \
        "a chapter with no counterpart on the site is being linked anyway"
    # And a linked record must not use our own index where the two differ.
    later = [d for d in docs if (d.get("kitab") or {}).get("index", 0) > 9
             and d.get("chapterLinkNumber")]
    assert later and all(d["chapterLinkNumber"] == d["kitab"]["index"] - 1 for d in later), \
        "chapters after الطلاق must map one lower than our own index"


def test_muwatta_chapter_links_survive_in_the_payload():
    """The kitab link must reach the reader, not merely the config.

    This regressed once without a test noticing. The Reader used to build the
    Muwatta's link from `kitab.index` directly; when Bulugh and the Shama'il
    made the build stamp `chapterLinkNumber` (matched by title against the
    witness JSON's `chapters`), the Reader switched to that field for every
    corpus — and the Muwatta's witness is a single-column CSV, so the matcher
    never ran, every number shipped null, and `corpus.chapterLink` kept
    claiming a link the UI could render on no record. Nothing failed: the
    gates measure binding, not linking.

    The corpus now declares `match: position` (its 61-to-61 correspondence is
    verified and pinned above), the build refuses a declared link that
    resolves NOTHING, and this test asserts on the shipped payload — the one
    artefact the earlier layers cannot vouch for.
    """
    import glob, json, pathlib
    cfg = corpus.load_config("muwatta")
    cl = (cfg.get("segmentation") or {}).get("chapter_link") or {}
    assert cl.get("match") == "position", \
        "the Muwatta's witness carries no chapters; only its verified " \
        "positional map can link it"
    docs = [json.loads(pathlib.Path(f).read_text(encoding="utf-8"))
            for f in glob.glob(str(corpus.ROOT.parent /
                                   "web/public/data/corpora/muwatta/hadith/matn-*.json"))]
    if not docs:
        pytest.skip("muwatta payload not built")
    linked = [d for d in docs if d.get("chapterLinkNumber") is not None]
    assert linked, "no muwatta record carries a chapter link — the regression is back"
    # Positional means OUR index, exactly — a drift here is a wrong book.
    assert all(d["chapterLinkNumber"] == (d.get("kitab") or {}).get("index")
               for d in linked), "positional link must equal our kitab index"
    # And every matn record under a kitab must carry one: 61 of 61 map.
    under = [d for d in docs if (d.get("kitab") or {}).get("index")]
    assert len(linked) == len(under), \
        f"{len(under) - len(linked)} matn records under a kitab ship no link"


def test_a_declared_chapter_link_that_resolves_nothing_fails_the_build():
    """Partial resolution is a text fact (Bulugh's الطلاق has no counterpart);
    TOTAL failure is a configuration error and must stop the build rather
    than ship a payload that claims a link and renders it nowhere. Pinned on
    the source, as the title-matching test above pins its mechanism, because
    running build.py end to end needs a bound corpus this test must not
    assume."""
    src = (corpus.ROOT / "build.py").read_text(encoding="utf-8")
    assert "if _cl and not _chapter_no:" in src and "return 1" in src, \
        "the zero-resolution guard is gone from build.py"


def test_payload_links_carry_only_the_contract_keys():
    """`corpus.chapterLink` and friends are ReferenceLink: label, labelAr,
    url. The yaml blocks carry pipeline-only keys besides (`level`, `match`,
    `layers`, `number_from_witness`), and shipping the dict verbatim leaked
    `level: bab` into the Shama'il's index.json — a key the contract does not
    declare and no component reads. The exporter now states the contract
    exactly; this holds it there."""
    import json, pathlib
    allowed = {"label", "labelAr", "url"}
    checked = 0
    for cid in CORPORA:
        idx = corpus.ROOT.parent / f"web/public/data/corpora/{cid}/index.json"
        if not idx.exists():
            continue
        doc = json.loads(idx.read_text(encoding="utf-8"))["corpus"]
        for field in ("referenceLink", "chapterLink", "recordLink"):
            link = doc.get(field)
            if link is None:
                continue
            checked += 1
            extra = set(link) - allowed
            assert not extra, f"{cid}.{field} ships undeclared keys {extra}"
    if not checked:
        pytest.skip("no built payload declares a link")

def test_bulugh_trailing_paragraphs_stay_in_the_matn():
    """The variants and takhrij sentences are the hadith's own text.

    Twice they were carved into a "takhrij" aside on the theory that a
    trailing paragraph is a footnote, and twice that shipped the hadith's own
    words — `وللبخاري: «…»`, `أخرجه الثلاثة` — as an apparatus block that a
    reader (correctly) read as footnotes attached to the wrong hadith. They
    are entry content: the witness carries hadith 6's matn AND its three
    variants inside one entry, and this edition numbers them as one hadith.
    So: no aside layer ships for this corpus, hadith 6's matn contains its
    variants, and the corpus index does not declare an aside layer it does
    not have. The real footnotes — the bodies behind the (1) anchors — are
    not in the source file at all, and no layer should pretend otherwise.
    """
    import glob, json, pathlib
    root = corpus.ROOT.parent / "web/public/data/corpora/bulugh"
    matns = glob.glob(str(root / "hadith/matn-*.json"))
    if not matns:
        pytest.skip("bulugh payload not built")
    assert not glob.glob(str(root / "hadith/takhrij-*.json")), \
        "a takhrij layer shipped — the carve-out is back"
    idx = json.loads((root / "index.json").read_text(encoding="utf-8"))
    assert idx["corpus"].get("asideLayer") is None, \
        "the corpus index declares an aside layer this corpus does not have"
    import re
    diac = re.compile("[\u064b-\u0652\u0670\u0640]")
    for f in matns:
        d = json.loads(pathlib.Path(f).read_text(encoding="utf-8"))
        if d.get("number") == 6:
            text = diac.sub("", d["leading"] + "".join(
                t["raw"] + t["punctuationAfter"] for t in d["tokens"]))
            assert "وللبخاري" in text, \
                "hadith 6 lost its Bukhari variant — the carve-out is back"
            break
    else:
        raise AssertionError("bulugh hadith 6 not found")


def test_the_aside_merge_machinery_stays_fixed():
    """`unnumbered_body_is_aside`, exercised on a fixture, since no corpus
    currently enables it. The machinery was wrong twice in SHAPE — one aside
    record per paragraph, and a whitespace collapse in close() that fused the
    merged notes back into a run-on — and both fixes should survive even
    while the flag has no user: several closed trailing paragraphs are ONE
    aside record with newline separators, a mid-clause continuation still
    joins with a space, and the body record never carries a newline."""
    import segment as seg
    cfg = {
        "id": "fixture",
        "segmentation": {
            "opener": r"^(\d+)\s*-\s*(.*)$",
            "unnumbered_body_is_aside": True,
            "layer_names": {"body": "matn", "aside": "note",
                            "top": "heading_kitab", "sub": "heading_bab",
                            "front": "frontmatter"},
            "heading_prefixes": ["كتاب", "باب"],
            "heading_top_prefixes": ["كتاب"],
        },
    }
    rules = seg.Rules.from_config(cfg)
    s = seg.Segmenter(cfg, rules)
    s.feed([
        "### | كتاب الفتن",
        "### | 1 - ",
        "# متن الحديث الأول قال. (1)",
        "# أخرجه فلان. (2)",     # matn is closed -> opens the aside
        "# وصححه غيره يعني",     # aside is closed -> a NEW note, newline
        "# في روايته. (3)",      # the note above is OPEN -> joins, space
        "# ورواه آخر. (4)",      # closed again -> a third note, newline
    ])
    s.finalise()
    notes = [r for r in s.records if r["layer"] == "note"]
    assert len(notes) == 1, f"{len(notes)} aside records for one hadith"
    assert notes[0]["textRaw"] == \
        "أخرجه فلان. (2)\nوصححه غيره يعني في روايته. (3)\nورواه آخر. (4)"
    matn = [r for r in s.records if r["layer"] == "matn"]
    assert len(matn) == 1 and "\n" not in matn[0]["textRaw"]


def test_every_lexical_source_is_wired_into_the_deploy_workflow():
    """
    A dictionary that CI never ingests ships as an empty section.

    THIS IS THE FAILURE THAT PROMPTED THE TEST. `build.py` degrades gracefully
    when an ingest is missing — it prints a note and sets `lisan_root` to null
    on every entry — which is right for a local run and silent in a deploy.
    Lisān and al-Nihāya went to production with a green build, a valid payload,
    correct contracts, passing tests, and no dictionary sections at all,
    because the deploy workflow was never told to fetch or ingest them.

    Registering a source in `corpora/` must be enough. Anything else that has
    to be remembered separately is a bug in the configuration surface, which is
    the same argument `ADDENDUM-adding-sources.md` makes about segment.py.
    """
    import yaml

    wf = (corpus.ROOT.parent / ".github" / "workflows" / "deploy.yml").read_text(
        encoding="utf-8"
    )
    for path in sorted((corpus.ROOT / "corpora").glob("*.yaml")):
        cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not corpus.is_lexical_source(cfg):
            continue
        cid = cfg["id"]
        assert f"--corpus {cid}" in wf, (
            f"deploy.yml never fetches the lexical source {cid!r} — its section "
            f"would render empty in production"
        )
        assert f"pipeline/{cid}.py" in wf, (
            f"deploy.yml never runs pipeline/{cid}.py — build.py would ship "
            f"{cid}_root as null on every entry and say nothing about it"
        )


def test_the_deploy_workflow_fails_when_an_ingest_is_missing():
    """Graceful degradation needs somewhere to be ungraceful."""
    wf = (corpus.ROOT.parent / ".github" / "workflows" / "deploy.yml").read_text(
        encoding="utf-8"
    )
    assert "Assert every dictionary was ingested" in wf
    assert "entries.json" in wf


def test_expensive_caches_are_not_keyed_on_dictionary_configs():
    """
    Editing a dictionary config must not re-run the morphological analysis.

    THE BUG THIS PINS. The morphology cache — the most expensive one in the
    build — was keyed on `hashFiles('pipeline/corpora/*.yaml')`. That glob also
    matches lane.yaml, lisan.yaml and nihaya.yaml, which `analyse.py` never
    reads: it walks `build/*/records.json`, and a lexical source never produces
    one. So editing a comment in a dictionary config threw away the cache and
    re-ran CAMeL over every corpus for nothing.

    The fix must stay DERIVED rather than listed. Naming the reading corpora
    explicitly in the workflow would work today and rot at the next corpus,
    and a forgotten corpus means a stale analysis silently reused — which is
    the failure the glob was widened to prevent in the first place.
    """
    wf = (corpus.ROOT.parent / ".github" / "workflows" / "deploy.yml").read_text(
        encoding="utf-8"
    )
    morph = next(l for l in wf.splitlines() if "key: morph-" in l)
    assert "corpora/*.yaml" not in morph, (
        "the morphology cache is keyed on every corpus config again, including "
        "the dictionaries analyse.py never opens"
    )
    assert "digests.outputs.reading" in morph, (
        "the morphology cache should be keyed on the reading-corpus digest"
    )
    assert "corpus_digest.py" in wf


def test_the_digest_separates_books_from_dictionaries():
    """The property the cache keys rely on, checked directly rather than
    trusted: a dictionary config must not move the reading digest."""
    import subprocess
    import sys

    def run(*args):
        return subprocess.run(
            [sys.executable, str(corpus.ROOT / "corpus_digest.py"), *args],
            capture_output=True, text=True, check=True,
        ).stdout.strip()

    reading, lexical = run(), run("--lexical")
    assert reading and lexical and reading != lexical

    path = corpus.ROOT / "corpora" / "lisan.yaml"
    original = path.read_bytes()
    try:
        path.write_bytes(original + b"\n# cache-key probe\n")
        assert run() == reading, "a dictionary edit moved the reading digest"
        assert run("--lexical") != lexical, "a dictionary edit left its own digest alone"
    finally:
        path.write_bytes(original)
