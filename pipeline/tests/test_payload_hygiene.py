"""
Display hygiene: the classes of defect a reader found on 2026-07-30.

Each test pins one class closed. The Khattab case (root chosen by ARABIC
ALPHABET among dictionary candidates) is pinned in test_analyse; these cover
what ships.
"""

import glob
import json
from pathlib import Path

import pytest

DATA = Path(__file__).resolve().parent.parent.parent / "web" / "public" / "data"


@pytest.fixture(scope="module")
def surface():
    out: dict = {}
    for f in sorted(glob.glob(str(DATA / "lex" / "surface-*.json"))):
        out.update(json.loads(Path(f).read_text(encoding="utf-8")))
    if not out:
        pytest.skip("payload not built")
    return out


def test_one_hamza_convention_in_roots(surface):
    """أرض beside ءرض taught a student two spellings of one radical."""
    offenders = [v["root"] for v in surface.values()
                 if v.get("root") and v["root"][0] in "أإآا"]
    offenders += [v["root"] for v in surface.values()
                  if v.get("root") and set(v["root"][1:]) & set("أإآؤئ")]
    assert not offenders, f"unfolded hamza in {len(offenders)} roots: {offenders[:5]}"


def test_no_unpronounceable_transliteration(surface):
    """أرْضٌ -> ʾrḍun shipped a pronunciation that does not exist."""
    vowels = set("aeiouāēīōū")
    bad = []
    for v in surface.values():
        d = (v.get("lemma_din") or "").lower()
        if len(d) > 1 and d[0] not in vowels and d[1].isalpha() and d[1] not in vowels:
            bad.append((v.get("lemma"), v.get("lemma_din")))
    assert not bad, f"{len(bad)} garbage transliterations: {bad[:5]}"


def test_no_empty_lane_senses(surface):
    """144 senses rendered as a bullet with nothing after it."""
    empty = 0
    for f in glob.glob(str(DATA / "lex" / "lane-*.json")):
        for doc in json.loads(Path(f).read_text(encoding="utf-8")).values():
            for ent in doc["entries"]:
                for s in ent["senses"]:
                    txt = "".join(r.get("v", "") for r in (s.get("runs") or [])
                                  if r.get("t") == "t").strip(" \t\n,.;·")
                    if not txt:
                        empty += 1
    assert empty == 0, f"{empty} empty Lane senses shipped"


def test_analyser_fallback_carries_its_basis(surface):
    """A reasoned root choice and an arbitrary one must be distinguishable."""
    missing = [v.get("unvocalized") for v in surface.values()
               if v.get("analysed") and v["analysed"].get("rootAlternatives")
               and not v["analysed"].get("rootBasis")]
    assert not missing, f"{len(missing)} disputed analyser roots with no basis"


def test_no_masked_radical_ever_ships(surface):
    """r13 masks weak radicals as '#'. Recovery resolves or DROPS; a student
    must never meet a '#' pretending to be a letter."""
    bad = []
    for v in surface.values():
        for r in [v.get("root"), v.get("contextRoot"),
                  *((v.get("analysed") or {}).get("rootAlternatives") or []),
                  (v.get("analysed") or {}).get("root")]:
            if r and "#" in r:
                bad.append((v.get("unvocalized"), r))
    assert not bad, f"masked radicals shipped: {bad[:5]}"
