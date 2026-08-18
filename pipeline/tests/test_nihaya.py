"""
al-Nihāya ingest: invariants shared with every dictionary, plus the pins that
caught real defects in this source specifically.
"""
import json
import re
from pathlib import Path

import pytest

from dictionaries import RESIDUAL, dict_root_variants
from normalise import root_key, root_variants

PIPELINE = Path(__file__).resolve().parents[1]
NIHAYA = PIPELINE / "build" / "nihaya" / "entries.json"
pytestmark = pytest.mark.skipif(
    not NIHAYA.exists(), reason="Nihāya not ingested here — run pipeline/nihaya.py"
)


@pytest.fixture(scope="module")
def nihaya():
    return json.loads(NIHAYA.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def senses(nihaya):
    return [s for p in nihaya.values() for e in p["entries"] for s in e["senses"]]


# ------------------------------------------------------------- invariants


def test_no_residual_markers(senses):
    bad = [r["v"][:80] for s in senses for r in s["runs"] if RESIDUAL.search(r["v"])]
    assert not bad, f"{len(bad)} runs carry markers, e.g. {bad[:2]}"


def test_the_stray_span_is_stripped(senses):
    """This conversion carries one unpaired `</span>`. Left in, it reaches a
    run and trips the audit — which is how it was found."""
    assert not any("span" in r["v"] for s in senses for r in s["runs"])


def test_no_harakat_are_invented(senses):
    marks = set("\u064b\u064c\u064d\u064e\u064f\u0650\u0651\u0652\u0670")
    assert not any(marks & set(r["v"]) for s in senses for r in s["runs"])


def test_units_are_sentences(senses):
    assert all(s["level"] == "sentence" for s in senses)


def test_root_keys_are_canonical(nihaya):
    assert all(r == root_key(r) and r for r in nihaya)


# -------------------------------------------------------------- the sigla


def test_sigla_are_normalised_and_present(senses):
    """(ه) and [ه] mean the same thing and both occur; one form is shown."""
    labels = {s["label"] for s in senses if s["label"]}
    assert labels <= {"(ه)", "(س)", "(ه)(س)", "(س)(ه)"}, labels
    labelled = sum(1 for s in senses if s["label"])
    assert labelled / len(senses) >= 0.34, "siglum share collapsed"


def test_siglum_pattern_is_unanchored():
    """The bug that silently emptied every label.

    The sigla open a `#` line in the source, so an anchored `^...` pattern
    looks right — and matches nothing, because the article is rejoined into
    continuous prose before the scan. Anchored, it found 0 of 10,467."""
    cfg = (PIPELINE / "corpora" / "nihaya.yaml").read_text(encoding="utf-8")
    line = next(l for l in cfg.splitlines() if l.strip().startswith("pattern:"))
    assert "^" not in line, "the siglum pattern is anchored again — labels will vanish"


# --------------------------------------------------------------- the pins


def test_expected_scale(nihaya):
    assert len(nihaya) == 4238


def test_no_bare_root_headings_are_accepted(nihaya):
    """The defect that corrupted an article outright.

    A bare-root pattern was tried and removed: it accepted 103 headings and
    recovered exactly ONE root the parenthesised pattern missed, while
    `### | صلا` — conversion damage sitting inside the صلم article — opened a
    spurious صلا entry that swallowed the rest of صلم's text. A reader looking
    up prayer got a paragraph about cropped ears."""
    salah = nihaya["صلا"]["entries"][0]["senses"][0]["runs"][0]["v"]
    assert "الصلاة" in salah[:40], f"صلا opens with the wrong article: {salah[:60]!r}"
    salm = nihaya["صلم"]["entries"][0]["senses"][0]["runs"][0]["v"]
    assert "الصلامات" in salm or "صلام" in salm


def test_structural_headings_do_not_eat_real_roots(nihaya):
    """حرف and فصل are both structural keywords AND genuine Arabic roots, so
    testing the structural filter first loses two articles."""
    assert "حرف" in nihaya and "فصل" in nihaya


def test_shares_the_alif_filing_convention(nihaya):
    """338 of its roots end in bare alif, same as Lisān — which is what turned
    a source-specific variant into a shared one."""
    assert any(v in nihaya for v in dict_root_variants("صلو"))
    assert not any(v in nihaya for v in root_variants("صلو"))


def test_it_is_selective_not_comprehensive(nihaya):
    """The reason it earns its own section rather than replacing Lisān: it is
    a dictionary of difficult words, roughly half Lisān's root count."""
    assert 4000 < len(nihaya) < 4500
