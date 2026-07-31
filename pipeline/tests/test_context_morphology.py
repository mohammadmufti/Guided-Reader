"""
Context disambiguation, and the narrow licence it has to override.

The temptation was to prefer the newer analyser wherever it disagreed. Measured
against Lane — does the word actually appear under that root's entry? — the
workbook wins disagreements roughly seven to one, so a general promotion would
have made the reader worse on most of them.

The exception is complete: geminate against hollow, the hollow-verb failure.
These tests pin both halves, because it is the ratio that justifies the rule.
"""

import json
from pathlib import Path

import pytest

from normalise import root_key

BUILD = Path(__file__).resolve().parent.parent / "build"
DATA = Path(__file__).resolve().parent.parent.parent / "web" / "public" / "data"
WEAK = set("وي")


@pytest.fixture(scope="module")
def context():
    """
    Every test here takes this fixture, including the two that read the payload
    rather than this file. That is deliberate: without it, a build that ran
    disambiguate.py AFTER build.py left the payload with no overrides, and two
    tests failed while a third skipped — three tests disagreeing about whether
    the provider was present. They should agree, and they should skip together
    on a corpus that has no context analysis at all.
    """
    path = BUILD / "tajrid" / "disambiguated.json"
    if not path.exists():
        pytest.skip("no context analysis — run pipeline/disambiguate.py before build.py")
    return json.loads(path.read_text(encoding="utf-8"))


def test_coverage_in_context(context, bindings):
    """99.5% measured. Context beats the 87.9% the type-level chain manages."""
    tokens = sum(len(r["tokens"]) for r in bindings.values())
    share = 100 * len(context) / tokens
    assert share > 95, f"only {share:.1f}% of tokens analysed in context"


def test_overrides_are_only_geminate_to_hollow(context):
    """
    The licence is narrow on purpose. If an override appears that is not this
    shape, the rule has been widened without the measurement being redone.
    """
    surface = {}
    for f in DATA.glob("lex/surface-*.json"):
        surface.update(json.loads(f.read_text(encoding="utf-8")))
    if not surface:
        pytest.skip("payload not built")

    seen = 0
    for path in list(DATA.glob("hadith/*.json"))[:400]:
        rec = json.loads(path.read_text(encoding="utf-8"))
        for tok in rec["tokens"]:
            new = tok.get("contextRoot")
            if not new:
                continue
            seen += 1
            old = (surface.get(tok["matchId"]) or {}).get("root")
            assert isinstance(old, str) and old.strip(), "override with no workbook root"
            a, b = root_key(old), root_key(new)
            assert len(a) == 3 and a[1] == a[2], f"{old} is not geminate"
            assert len(b) == 3 and b[1] in WEAK, f"{new} is not hollow"
    assert seen > 0, "no overrides found — has the rule stopped firing?"


def test_the_hollow_verbs_are_mostly_right(context):
    """
    The words that motivated all of this. كُنْتُ is from ك-و-ن; a doubled ن is
    the shape you get by reconstructing a vanished weak radical wrongly.

    Not all of them: `وَكُنْتُ` is recorded with root `وكن`, the conjunction
    swallowed into the root. That is a DIFFERENT workbook bug — three letters,
    but not the geminate shape — and the override deliberately does not fire on
    it, because no measurement has been done to say context is better there.
    Twelve tokens. The floor below is where that residue sits.
    """
    surface = {}
    for f in DATA.glob("lex/surface-*.json"):
        surface.update(json.loads(f.read_text(encoding="utf-8")))
    if not surface:
        pytest.skip("payload not built")

    checked = right = 0
    for path in DATA.glob("hadith/*.json"):
        rec = json.loads(path.read_text(encoding="utf-8"))
        for tok in rec["tokens"]:
            if tok["raw"] not in ("كنت", "وكنت", "كنا", "وكنا"):
                continue
            root = tok.get("contextRoot") or (surface.get(tok["matchId"]) or {}).get("root")
            if root:
                checked += 1
                if root_key(root) == root_key("كون"):
                    right += 1
    assert checked > 100, f"only {checked} tokens of this class found"
    share = 100 * right / checked
    assert share >= 88, f"only {share:.0f}% of كنت/كنا resolve to كون ({right}/{checked})"
