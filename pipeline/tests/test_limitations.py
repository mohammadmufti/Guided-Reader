"""
The user-facing figures must be true.

`LIMITATIONS.md` and `/about` tell a reader how much to trust each word. Those
pages were stale for several releases — they still claimed a Tier 1 reading was
"not in doubt" after the الأعمال case had shown it was not. Numbers in a
document decay silently; numbers in a test do not.
"""

import collections
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
LIMITATIONS = ROOT / "LIMITATIONS.md"
ABOUT = ROOT / "web" / "src" / "routes" / "Limitations.tsx"
TOLERANCE = 0.15  # percentage points


@pytest.fixture(scope="module")
def shares(bindings):
    c = collections.Counter()
    for rec in bindings.values():
        for t in rec["tokens"]:
            c[(t["binding"], t["confidence"])] += 1
    total = sum(c.values())
    return {k: 100 * v / total for k, v in c.items()}, total


def _percentages(text):
    return {float(m) for m in re.findall(r"(\d+\.\d)%", text)}


@pytest.mark.parametrize("page", [LIMITATIONS, ABOUT])
def test_documented_shares_are_current(page, shares):
    """Every tier share quoted on the page must match what the build produced."""
    pct, _ = shares
    text = page.read_text(encoding="utf-8")
    quoted = _percentages(text)
    for key, value in pct.items():
        if value < 1:
            continue
        assert any(abs(q - value) <= TOLERANCE for q in quoted), (
            f"{page.name} does not quote {value:.1f}% for {key}; it quotes {sorted(quoted)}"
        )


@pytest.mark.parametrize("page", [LIMITATIONS, ABOUT])
def test_guess_rate_is_current(page, shares):
    """`one word in every N` must match the Tier 4 share."""
    pct, total = shares
    expected = round(100 / pct[("heuristic", "low")])
    text = page.read_text(encoding="utf-8")
    found = [int(m) for m in re.findall(r"one word in every\s*(?:<[^>]+>)?\s*(\d+)", text)]
    assert found, f"{page.name} does not state a guess rate"
    assert any(abs(f - expected) <= 2 for f in found), (
        f"{page.name} says 1 in {found}, current is 1 in {expected}"
    )


def test_no_longer_claims_tier_1_is_beyond_doubt():
    """
    The specific sentence the الأعمال case disproved. Tier 1 means the lexicon
    offered one candidate, not that the candidate is right.
    """
    text = LIMITATIONS.read_text(encoding="utf-8")
    assert "| Only one entry matches the spelling | 50.3% | **Not in doubt** |" not in text
