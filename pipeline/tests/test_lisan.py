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

LISAN = Path(__file__).resolve().parents[1] / "build" / "lisan" / "entries.json"
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
