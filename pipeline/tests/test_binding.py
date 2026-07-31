"""
Token binding: coverage, and how much each tier is worth.

The gate the spec sets is Tier 1+2 >= 90% of matn tokens. The figures that
matter more day to day are the held-out accuracies of the lower tiers, because
they are what the interface promises a reader.
"""

import collections

import pytest

TIER = {
    ("unique", "high"): 1,
    ("unique", "medium"): 1,
    ("aligned", "high"): 2,
    ("heuristic", "medium"): 3,
    ("heuristic", "low"): 4,
    ("unbound", "none"): 5,
}

GATE = 90.0
NAIVE_CEILING = 85.9  # always take the most frequent candidate


@pytest.fixture(scope="module")
def tiers(bindings, records):
    layer = {r["id"]: r["layer"] for r in records["records"]}
    matn = collections.Counter()
    everything = collections.Counter()
    for rid, rec in bindings.items():
        for t in rec["tokens"]:
            tier = TIER[(t["binding"], t["confidence"])]
            everything[tier] += 1
            if layer[rid] == "matn":
                matn[tier] += 1
    return matn, everything


def test_tier_1_and_2_clear_the_gate(tiers):
    matn, _ = tiers
    total = sum(matn.values())
    witnessed = 100 * (matn[1] + matn[2]) / total
    assert witnessed >= GATE, f"{witnessed:.1f}% < {GATE}%"
    assert witnessed > NAIVE_CEILING, "no better than always guessing the commonest"


def test_unbound_is_negligible(tiers):
    _, everything = tiers
    assert everything[5] < 50, f"{everything[5]} unbound tokens — the join key may be wrong"


def test_every_token_has_a_provenance(bindings):
    for rec in bindings.values():
        for t in rec["tokens"]:
            assert (t["binding"], t["confidence"]) in TIER, (t["binding"], t["confidence"])
            assert t["clickable"] == (t["matchId"] is not None)
            if t["matchId"] is None:
                assert t["surface"] == t["raw"]


def test_honorific_case_is_right(bindings):
    """
    al-Tajrid rewrites Bukhari's isnad openings, which CHANGES THE CASE:
    `سمعت عمرَ بنَ الخطاب` becomes `عن عمرَ بنِ الخطاب`. Alignment transferred
    Bukhari's vowelling verbatim and got 194 of 491 wrong. Bukhari is categorical
    here, so this is checkable rather than a matter of taste.
    """
    after = collections.Counter()
    for rec in bindings.values():
        toks = rec["tokens"]
        for i, t in enumerate(toks):
            if t["raw"] == "بن" and i >= 2 and toks[i - 2]["raw"] == "عن":
                after[t["surface"]] += 1
    wrong = sum(v for k, v in after.items() if k != "بْنِ")
    assert wrong == 0, f"{wrong} of {sum(after.values())} `عن X بن` openings not majrur: {dict(after)}"


def test_inna_takes_the_nominative(bindings):
    """
    `إنما` is كافة ومكفوفة — it strips إن of its governance, so the noun after it
    is مبتدأ مرفوع. `إِنَّمَا الْأَعْمَالُ`, never الْأَعْمَالِ. The lexicon held only
    the genitive form, and Tier 1 claimed the token before alignment could
    object.
    """
    bad = []
    for rid, rec in bindings.items():
        toks = rec["tokens"]
        for i, t in enumerate(toks):
            if i and toks[i - 1]["raw"] in ("إنما", "وإنما") and t["raw"] == "الأعمال":
                if not t["surface"].endswith("ُ"):
                    bad.append((rid, t["surface"]))
    assert not bad, f"majrur after إنما: {bad}"


def test_root_index_covers_the_content_words(bindings, records, expected):
    """
    Root search only helps where roots exist. 51.9% of tokens carry one; if that
    collapses, the feature has quietly stopped working. The floors are the
    corpus's own — fixtures/{corpus}.yaml.
    """
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parent.parent.parent / "web" / "public" / "data" / "search.json"
    if not path.exists():
        pytest.skip("payload not built")
    data = json.loads(path.read_text(encoding="utf-8"))
    roots = data.get("roots", {})
    assert len(roots) > expected("binding.min_roots_indexed"), (
        f"only {len(roots)} roots indexed"
    )
    tokens = sum(len(e) - 1 for entries in roots.values() for e in entries)
    total = sum(len(r["tokens"]) for r in bindings.values())
    share = 100 * tokens / total
    lo, hi = (expected("binding.root_coverage_pct")[k] for k in ("min", "max"))
    assert lo < share < hi, f"roots cover {share:.1f}% of tokens — expected {lo}–{hi}%"
