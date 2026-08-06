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


@pytest.mark.parametrize("page", [LIMITATIONS])
def test_documented_shares_are_current(page, shares):
    """Every tier share quoted on the page must match what the build produced.

    LIMITATIONS.md only. `/about` no longer quotes figures at all: it reads
    `index.binding`, measured per corpus at build time, because al-Tajrid's
    shares are false for the other three books and meaningless for the one
    bound off its own harakat.
    """
    pct, _ = shares
    text = page.read_text(encoding="utf-8")
    quoted = _percentages(text)
    for key, value in pct.items():
        if value < 1:
            continue
        assert any(abs(q - value) <= TOLERANCE for q in quoted), (
            f"{page.name} does not quote {value:.1f}% for {key}; it quotes {sorted(quoted)}"
        )


def test_no_longer_claims_tier_1_is_beyond_doubt():
    """
    The specific sentence the الأعمال case disproved. Tier 1 means the lexicon
    offered one candidate, not that the candidate is right.
    """
    text = LIMITATIONS.read_text(encoding="utf-8")
    assert "| Only one entry matches the spelling | 50.3% | **Not in doubt** |" not in text


def test_about_page_reads_its_figures_rather_than_quoting_them():
    """/about must describe the book being read, not one book's numbers.

    This file used to assert that Limitations.tsx quoted the measured shares as
    literals, and kept them honest for a single corpus. With four corpora the
    literals were false three times out of four — al-Tajrid's 49.5% aligned
    said nothing about a text bound off its own harakat. The page now reads
    `index.binding`, which the build measures per corpus, so the thing to pin
    is that it still does.
    """
    src = ABOUT.read_text(encoding="utf-8")
    assert "index?.binding" in src or "index.binding" in src, \
        "the About page must take its figures from the payload"
    # No stale hardcoded share should creep back in.
    for stale in ("49.5%", "45.8%", "2.1%\"", "1.5%\""):
        assert stale not in src, f"hardcoded share {stale} is back in the About page"
