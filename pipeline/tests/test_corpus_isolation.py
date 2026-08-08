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
    assert '"classical", "lane"' in src


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
        if cid in ("lane", "rawd"):
            continue          # reference data and a segmentation-only corpus
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

    missed = [
        e for e in entries.values()
        if e.get("root") and not e.get("lane_root")
        and any(v in lane for v in root_variants(str(e["root"])))
    ]
    assert not missed, (
        f"{len(missed)} entries have a root Lane holds but carry no lane_root, "
        f"e.g. {[(x.get('vocalized'), x.get('root')) for x in missed[:3]]}"
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
