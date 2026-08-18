"""
Lisān linking: the root variant extension, the closed-class rule, and the
shard invariant. Each case here is one a measurement found, not one imagined.
"""
import json
from pathlib import Path

import pytest

from build import CLOSED_CLASS_POS
from lisan import lisan_root_variants
from normalise import root_variants

PIPELINE = Path(__file__).resolve().parents[1]
LISAN = PIPELINE / "build" / "lisan" / "entries.json"
pytestmark = pytest.mark.skipif(
    not LISAN.exists(), reason="Lisān not ingested here — run pipeline/lisan.py"
)


@pytest.fixture(scope="module")
def lisan():
    return json.loads(LISAN.read_text(encoding="utf-8"))


# ------------------------------------------------------- the alif extension


def test_alif_variant_reaches_final_weak_roots(lisan):
    """The gotcha worth 7.5 points of coverage.

    Ibn Manẓūr files final-weak roots under bare alif — صلا, not صلو. Without
    the extension every final-weak root in every corpus misses its article and
    the reader sees a section with nothing in it."""
    assert any(v in lisan for v in lisan_root_variants("صلو"))
    assert not any(v in lisan for v in root_variants("صلو"))


def test_shared_root_variants_are_not_widened():
    """The extension must stay source-scoped.

    Lane holds 213 alif-final roots of its own, so widening `root_variants()`
    would move live Lane resolution and silently re-point entries that are
    currently correct. If this fails, someone edited the shared function —
    re-measure Lane before deleting the test."""
    assert "صلا" not in root_variants("صلو")
    assert "صلا" in lisan_root_variants("صلو")


def test_extension_is_a_superset(lisan):
    """It only ever ADDS candidates. A variant the shared function produces
    must survive, or the extension is silently changing Lane-era behaviour."""
    for root in ("صلو", "كتب", "قول", "نبا", "رجل"):
        assert set(root_variants(root)) <= set(lisan_root_variants(root))


# --------------------------------------------------------- the closed class


def test_closed_class_words_reach_no_article(lisan):
    """The rule that costs 7.6% of the corpus in wrong articles when absent.

    Lane's rescue — link only where the article holds this word's own headword
    — is unstateable here, because there are no per-headword entries. So the
    only available rule would be mere existence, which is exactly what cost two
    CI failures on Lane. Measured with CAMeL over every closed-class form in
    al-Tajrīd: 644 forms / 9,704 tokens would otherwise open an article whose
    subject the word has nothing to do with."""
    hazards = {
        "ذَلِكَ": "ذلل",       # to be lowly, abased
        "اللَّهُمَّ": "لهم",   # to swallow greedily
        "فَمَا": "فمم",        # mouth
        "حَتَّى": "حتت",       # to scrape off
        "فَلَمَّا": "لمم",     # to gather, touch lightly
    }
    for form, camel_root in hazards.items():
        assert camel_root in lisan, (
            f"{camel_root} is expected to BE a real article — that is why "
            f"linking {form} to it would look plausible and be wrong"
        )
    src = (PIPELINE / "build.py").read_text(encoding="utf-8")
    assert "_pos not in CLOSED_CLASS_POS" in src, (
        "build.py no longer gates Lisān linking on the closed class"
    )


def test_share_scrubs_closed_class_links_too():
    """A corpus whose analyser was less sure can gap-fill a link the build
    refused, so the merge has to hold the same line."""
    src = (PIPELINE / "share.py").read_text(encoding="utf-8")
    assert 'e.get("lisan_root")' in src and "scrubbed_lisan" in src


def test_closed_class_pos_covers_both_taggers():
    """The rule is only as good as the label. Both the workbook's vocabulary
    and the analyser's must be in the set, or the gate has a hole."""
    assert {"pronoun", "particle", "stopword"} <= set(CLOSED_CLASS_POS)


# ------------------------------------------------------------- the plumbing


def test_shard_set_is_wired_everywhere():
    """`fnv1a` is implemented twice — build.py and web/src/lib/lexicon.ts — and
    each new shard set widens that seam. The build-time assertion that every
    reference resolves in its own shard is what catches drift."""
    build = (PIPELINE / "build.py").read_text(encoding="utf-8")
    assert "missing_lisan" in build, "no orphan check for lisan_root"
    assert '"lisan": lisan_shards_n' in build, "shard count is not in the index"
    lex = (PIPELINE.parent / "web" / "src" / "lib" / "lexicon.ts").read_text(encoding="utf-8")
    assert "sharedLisan" in lex and "lisan-" in lex


def test_lisan_is_fetched_independently_of_lane_root():
    """Lisān holds 8,973 roots against Lane's 5,160, so a word can have an
    Arabic article and no English one. Hanging the fetch off the `lane_root`
    early return silently dropped exactly the words this source was added to
    serve — caught in review, and pinned here."""
    lex = (PIPELINE.parent / "web" / "src" / "lib" / "lexicon.ts").read_text(encoding="utf-8")
    head = lex.split("if (!entry.lane_root)")[0]
    assert "loadLisan(entry.lisan_root" in head, (
        "the Lisān fetch moved below the lane_root early return"
    )


def test_lane_payload_declares_a_null_volume():
    """`vol` is shared with a multi-volume source now. A missing key is not the
    same as a known absence, and the client distinguishes them."""
    build = (PIPELINE / "build.py").read_text(encoding="utf-8")
    assert '"vol": None' in build
