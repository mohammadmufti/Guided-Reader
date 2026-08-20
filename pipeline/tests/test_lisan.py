"""
Lisān al-ʿArab ingest: the invariants, and the pins that caught real defects.

Split the way conftest describes. The invariants must hold for any dictionary
ingested into the shared store — no residual markers, no empty sections, runs
flattened, no fabricated sense structure. The pins are properties of this
digitisation at its recorded checksum.
"""
import json
import re
import unicodedata
from pathlib import Path

import pytest

from normalise import root_key, root_variants

PIPELINE = Path(__file__).resolve().parents[1]
LISAN = PIPELINE / "build" / "lisan" / "entries.json"
pytestmark = pytest.mark.skipif(
    not LISAN.exists(), reason="Lisān not ingested here — run pipeline/lisan.py"
)


@pytest.fixture(scope="module")
def lisan():
    return json.loads(LISAN.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def runs(lisan):
    return [
        run
        for payload in lisan.values()
        for e in payload["entries"]
        for s in e["senses"]
        for run in s["runs"]
    ]


# ------------------------------------------------------------------ invariants


def test_no_residual_markers(runs):
    """ADDENDUM §A.5 calls this the single most useful signal that a config is
    right. If a marker survives into a run, the strip patterns are wrong and
    everything downstream is built on garbage."""
    bad = re.compile(r"###|~~|PageV\d|<div|\bms\d{3,}\b|\[\s*ص\s*:")
    offenders = [r["v"][:80] for r in runs if bad.search(r["v"])]
    assert not offenders, f"{len(offenders)} runs carry markers, e.g. {offenders[:2]}"


def test_no_empty_sections(lisan):
    """A section with nothing to say is not rendered — the panel's own rule,
    enforced upstream so the panel never has to. `هرث`, whose whole article is
    a footnote marker, is dropped at ingest for exactly this reason."""
    for root, payload in lisan.items():
        assert payload["entries"], root
        for e in payload["entries"]:
            assert e["senses"], f"{root} has an entry with no senses"
            for s in e["senses"]:
                assert s["runs"], f"{root} has a sense with no runs"
                assert all(r["v"].strip() for r in s["runs"]), root


def test_runs_are_flattened_not_markup(runs):
    """The run model is a security boundary, not a convenience: the client
    renders without an HTML parser, so no source may smuggle markup through."""
    assert all(set(r) == {"t", "v"} for r in runs)
    assert {r["t"] for r in runs} <= {"t", "ar", "i", "ref", "q", "trop"}
    assert not any("<" in r["v"] and ">" in r["v"] for r in runs)


def test_no_fabricated_sense_structure(lisan):
    """Ibn Manẓūr wrote no sense numbers. ROADMAP principle 2: inventing them
    reproduces the sampled-sense error with more confidence. Units are the
    edition's sentences and must say so."""
    for payload in lisan.values():
        for e in payload["entries"]:
            for s in e["senses"]:
                assert s["label"] is None
                assert s["level"] == "sentence"


def test_units_are_sentences_not_line_fragments(lisan):
    """The defect this parser exists to fix. Raw `#` lines are not paragraphs:
    52.5% run under 60 characters and 55.5% end mid-sentence, because Shamela
    breaks around block quotations and verse. Rejoining and splitting on
    terminal punctuation is what recovers readable units."""
    lens = [
        len(run["v"])
        for payload in lisan.values()
        for e in payload["entries"]
        for s in e["senses"]
        for run in s["runs"]
    ]
    short = sum(1 for x in lens if x < 60) / len(lens)
    assert short < 0.45, f"{short:.1%} of units under 60 chars — rejoin regressed"


def test_the_harakat_are_the_editors_own(runs):
    """
    THIS TEST WAS INVERTED. It used to assert that NO mark ever appeared,
    because every OpenITI version of this book is stripped — all four were
    checked and each has exactly zero combining marks. Shamela's own
    distribution of the same edition keeps them: 8.4 million of them, ratio
    0.636 against Lane's 0.761.

    DIACRITISATION.md §4 is untouched. That rule forbids INVENTING
    vocalisation; these are the editors' vowels as printed, and `lisan.py`
    refuses any entry whose de-diacritised text does not reproduce the
    independently-derived OpenITI text it replaces.
    """
    marks = sum(
        1 for r in runs for c in r["v"] if unicodedata.category(c).startswith("M")
    )
    letters = sum(1 for r in runs for c in r["v"] if "\u0621" <= c <= "\u064a")
    ratio = marks / letters
    assert ratio > 0.55, (
        f"harakat ratio {ratio:.3f} — the Shamela .bok did not take, and the "
        "panel has quietly gone back to bare consonants"
    )


def test_unverified_entries_keep_their_bare_text(lisan):
    """A doubtful substitute is worse than a bare one.

    Where the vocalised text does not verify against the OpenITI text it would
    replace, the entry keeps what it had. That is a small, bounded, honest
    residue — not a defect to paper over."""
    bare = [
        k for k, v in lisan.items()
        if not any(
            unicodedata.category(c).startswith("M")
            for s in v["entries"][0]["senses"] for c in s["runs"][0]["v"]
        )
    ]
    assert len(bare) / len(lisan) < 0.02, f"{len(bare)} entries unvocalised"


def test_root_keys_are_canonical(lisan):
    """The join key. A root filed under anything but `root_key` is unreachable
    from the surface entries that point at it."""
    for root in lisan:
        assert root == root_key(root), root
        assert root


# ------------------------------------------------------------------- the pins


def test_expected_scale(lisan):
    assert len(lisan) == 8973


def test_page_provenance_is_present(lisan):
    """The OpenITI annotator collated this digitisation's pagination against
    the printed Dār Ṣādir edition, so vol/page is citable and a reader can
    check us against a physical book. Worth asserting for that reason."""
    with_page = sum(1 for p in lisan.values() if p["page"] is not None)
    assert with_page / len(lisan) >= 0.98
    assert (lisan["صلا"]["vol"], lisan["صلا"]["page"]) == (14, 463)


def test_salah_opens_with_the_definition(lisan):
    """The canonical case, and the whole argument for this source. v1 showed
    ṣalāh as 'the middle of the back of a human being'; Lane's own entry opens
    'Prayer, supplication, or petition'; Ibn Manẓūr opens with the classical
    definition, first, with no ranking heuristic and no sampling."""
    first = lisan["صلا"]["entries"][0]["senses"][0]["runs"][0]["v"]
    bare = "".join(c for c in first if not unicodedata.category(c).startswith("M"))
    assert bare.startswith("الصلاة: الركوع والسجود")
    # And now with the vowels the reader actually needs. Asserted by counting
    # marks rather than by matching a literal: mark ORDER on a letter is not
    # normalised in this text, so a hand-typed comparison string is a trap.
    marks = sum(1 for c in first[:20] if unicodedata.category(c).startswith("M"))
    assert marks >= 4, f"the opening definition lost its harakat: {first[:40]!r}"


def test_final_weak_roots_are_filed_under_alif(lisan):
    """The gotcha that costs 7.5 points of coverage if missed. This book files
    final-weak roots under bare alif — صلا, not صلو or صلى — and
    `root_variants()` handles the weak axis as ي/ى/و only. `build.py` must
    therefore extend the variants for this source; it must NOT edit
    `root_variants()` itself, because Lane holds 213 alif-final roots of its
    own and the change would move live Lane resolution."""
    assert "صلا" in lisan
    assert not {"صلو", "صلى"} & set(lisan)
    assert not any(v in lisan for v in root_variants("صلو")), (
        "root_variants() now reaches صلا — if that was deliberate, re-measure "
        "Lane resolution before deleting this test"
    )


def test_line_separator_is_normalised():
    """
    The bug that silently un-vocalised the whole dictionary.

    Shamela stores page text with bare \\r between the edition's lines.
    `mdb-export` rewrote those to \\n on its way through CSV, so splitting on
    "\\n" worked for exactly as long as the reader was mdbtools — and found
    nothing the moment it was not. 83 entries vocalised instead of 8,929, with
    the ingest reporting success. Only the harakat floor caught it.

    An entry head is defined by being at the start of a LINE. Which byte the
    source uses for that is not something the parser should know.
    """
    import lisan_vocalised

    for sep in ("\n", "\r", "\r\n"):
        page = sep.join(["فصل الهمزة", "أَبَأَ: قَالَ الشَّيْخُ", "ثانٍ من الكلام"])
        got = lisan_vocalised.candidate_entries([
            {"nass": page, "part": "1", "page": "23", "id": 1}
        ])
        assert len(got) == 1, f"separator {sep!r}: found {len(got)} entries"
        assert got[0]["root"] == root_key("أبأ")


def test_the_reader_needs_no_system_package():
    """A build should not need a package manager to read a file it already has.

    The previous implementation shelled out to `mdb-export`, so CI ran
    `apt-get install mdbtools` on every cold runner. That step hung for six
    hours and was killed by the job timeout — apt blocks indefinitely when the
    runner's background unattended-upgrades holds the dpkg lock."""
    src = (PIPELINE / "lisan_vocalised.py").read_text(encoding="utf-8")
    assert "subprocess" not in src.split('"""', 2)[-1], "the ingest shells out again"
    wf = (PIPELINE.parent / ".github" / "workflows" / "deploy.yml").read_text(encoding="utf-8")
    assert "apt-get" not in wf, "an apt-get step is back in the deploy workflow"
    assert "access-parser" in wf, "the pure-Python reader is not installed in CI"


def test_distinct_roots_are_not_concatenated(lisan):
    """
    بدأ (to begin) and بدا (to appear) are DIFFERENT ROOTS.

    `root_key` folds hamza to bare alif so that CAMeL's spelling of a root and
    the book's can meet. That is right for matching and wrong as an identity:
    142 keys carry two genuinely different roots. They used to be concatenated
    into one article, on the reasoning that dropping one would lose it. Not
    dropping was right; concatenating was not — a reader opening بدا got 153
    units, 89 on beginning and then, with no break at all, a different root's
    article on appearing.
    """
    entry = lisan["بدا"]["entries"]
    assert len(entry) == 2, "بدأ and بدا have been merged again"
    heads = {e["headword"] for e in entry}
    assert heads == {"بدأ", "بدا"}
    first = {e["headword"]: e["senses"][0]["runs"][0]["v"] for e in entry}
    assert "المُبْدئ" in first["بدأ"] or "أَنْشَأَ" in first["بدأ"]
    assert "ظَهَرَ" in first["بدا"] or "يَبْدُو" in first["بدا"]


def test_the_book_s_spelling_is_preserved(lisan):
    """The panel shows `headword`, not the key.

    The key is a join artefact. Rendering it told the reader بدا where Ibn
    Manẓūr wrote بدأ, on 17.9% of shipped entries — quiet wrongness of exactly
    the kind the sampled-sense bug was."""
    differing = [
        (k, e["headword"])
        for k, v in lisan.items()
        for e in v["entries"]
        if e["headword"] != k
    ]
    assert differing, "no key differs from its spelling — folding may have stopped"
    for key, head in differing:
        assert root_key(head) == key, f"{head!r} does not fold to its key {key!r}"


def test_one_article_per_source_head(lisan):
    """Each entry is one article, and nodeid identifies it.

    Using the key as nodeid made the two roots under a folded key
    indistinguishable to anything downstream."""
    for key, payload in lisan.items():
        ids = [e["nodeid"] for e in payload["entries"]]
        assert len(ids) == len(set(ids)), f"{key}: duplicate nodeids {ids}"
        for e in payload["entries"]:
            assert e["nodeid"] == e["headword"]
