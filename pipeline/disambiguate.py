#!/usr/bin/env python3
"""
Context-level morphology, via `farahidi` — a pure-Python port of Alkhalil
Morpho Sys 2.

    python pipeline/disambiguate.py --corpus tajrid

WHY THIS IS DIFFERENT FROM THE OTHER PROVIDERS. Everything else in the lexicon is
type-level: a form has a lemma, a lemma has a root. That works until the form is
ambiguous, and Arabic's hardest cases are exactly the ambiguous ones. `كُنْتُ`
alone could be several things; `وَكُنْتُ أَطُوفُ` is not ambiguous at all.

So this runs over RECORDS, not over the form inventory, and disambiguates each
token against its neighbours. Coverage is 99.4% of tokens in context against
87.9% for the type-level chain.

WHAT IT IS ALLOWED TO OVERRIDE, AND WHY SO LITTLE.

Measured against Lane — not "is this string a root somewhere", which cannot tell
a real root from a coincidence, but "does this word actually appear under that
root's entry" — the supplied workbook wins disagreements **1,489 to 214**. So
this provider does NOT get general precedence: promoting it wholesale would make
the reader worse on seven cases out of eight.

There is one class where it wins completely. Where the workbook produces a
GEMINATE root and this produces a HOLLOW one, Lane backs this provider **18 times
out of 18, with zero for the workbook**. That is the hollow-verb failure exactly:
`كُنْتُ` recorded as كنن when it is كون, `يَطُفْ` as طفف when it is طوف. Weak
middle radicals disappear in the surface form and a type-level analyser
reconstructs a doubled consonant instead.

So precedence is: workbook, EXCEPT where it offers a geminate and this offers a
hollow root, and except where it offers nothing at all.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "build"

sys.path.insert(0, str(ROOT))
from corpus import inline_strip_patterns, load_config
from tokenise import tokenise  # noqa: E402

WEAK = set("وي")


def is_geminate(root: str) -> bool:
    """Last two radicals identical — the shape a hollow verb is mistaken for."""
    return len(root) == 3 and root[1] == root[2]


def is_hollow(root: str) -> bool:
    """Weak middle radical: the shape that disappears in the surface form."""
    return len(root) == 3 and root[1] in WEAK


# The fields the analyser carries and the disambiguator drops. Named here so
# that adding one is a change in a single place, and so that the emitted record
# cannot silently gain a field nothing has measured.
GRAMMAR_FIELDS = (
    "case_or_mood",
    "part_of_speech",
    "pattern_stem",
    "pattern_lemma",
    "proclitic",
    "enclitic",
    "stem",
    "voweled_word",
)

# Alkhalil writes an absent value as `-` for a tag and `#` for a clitic slot.
# An absent value is NOT a value: kept, it would put a bare dash in the panel
# and a meaningless bucket in every measurement over this file.
EMPTY = {"", "-", "#", "none", "None"}


def grammar_of(result, analyser, cache: dict[str, list]) -> dict:
    """
    The context-chosen analysis, in full.

    WHY THIS IS NOT SIMPLY `analyser.analyze(token)[0]`. Out of context the
    first solution is frequently wrong — this is the whole reason the
    disambiguation stage exists. So the disambiguator picks the reading, and
    this recovers the fields it discarded by matching on what it did keep.

    Matching is on (lemma, root, stem) and falls back to (lemma, root). A token
    whose solutions do not agree on the grammar after that is left with no
    grammar at all rather than an arbitrary one: this file feeds a panel that
    tells a student what case a word is in, and a plausible guess there is
    worse than a blank.
    """
    token = result.token
    if token not in cache:
        try:
            cache[token] = analyser.analyze(token) or []
        except Exception:
            cache[token] = []
    solutions = cache[token]
    if not solutions:
        return {}

    exact = [s for s in solutions
             if s.lemma == result.lemma and s.root == result.root
             and s.stem == result.stem]
    chosen = exact or [s for s in solutions
                       if s.lemma == result.lemma and s.root == result.root]
    if not chosen:
        return {}

    out: dict[str, object] = {}
    for field in GRAMMAR_FIELDS:
        values = {getattr(s, field, None) for s in chosen}
        values = {str(v).strip() for v in values if v is not None}
        values -= EMPTY
        # AGREEMENT OR NOTHING. Where the surviving solutions disagree on a
        # field, the disambiguation did not settle it, and picking the first is
        # picking at random.
        if len(values) == 1:
            out[field] = values.pop()
    tags = [t.strip() for t in str(out.pop("part_of_speech", "")).split("|")]
    tags = [t for t in tags if t and t not in EMPTY]
    if tags:
        out["tags"] = tags
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", default="tajrid")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    records_path = OUT / args.corpus / "records.json"
    if not records_path.exists():
        print(f"no records at {records_path}; run segment.py first", file=sys.stderr)
        return 1

    # THE ANALYSER READS THE VOWELS. It does not infer i`rab from syntax, and
    # this was measured: hide the mark on the last consonant and its accuracy
    # falls from 96.1% to 52.1% while its coverage falls by a factor of twelve.
    # So what it is given matters more than anything else in this file.
    #
    # `records.json` is the text as the corpus supplies it, and OpenITI strips
    # diacritics from twelve of our thirteen corpora. Feeding it that is asking
    # the analyser to do the one thing it cannot.
    #
    # `bindings.json` carries the VOCALISED form of each token, which the
    # pipeline has already worked out from the source or from a witness. On
    # al-Tajrid, switching the input from `raw` to `surface`:
    #
    #     input = raw       predictions   275   accuracy 71.4%
    #     input = surface   predictions 1,660   accuracy 97.1%
    #
    # This is why disambiguate.py must run AFTER bind.py, not before it.
    bindings_path = OUT / args.corpus / "bindings.json"
    bindings = {}
    if bindings_path.exists():
        bindings = json.loads(bindings_path.read_text(encoding="utf-8"))
    else:
        print("  (no bindings — falling back to the raw source text, which is "
              "unvowelled for every corpus but riyad; run bind.py first)")

    try:
        from farahidi import Analyzer, Disambiguator
    except ImportError:
        print("farahidi is not installed — pip install farahidi", file=sys.stderr)
        return 1

    records = json.loads(records_path.read_text(encoding="utf-8"))["records"]
    if args.limit:
        records = records[: args.limit]

    strip = inline_strip_patterns(load_config(args.corpus))
    disambiguator = Disambiguator()
    # The disambiguator returns a REDUCED result — token, lemma, root, stem —
    # and drops the analysis it chose them from. The analyser returns the whole
    # thing: case, mood, the tag bundle, both waznes, the typed clitics. So the
    # chosen reading is recovered by asking the analyser for this token's
    # solutions and taking the one the disambiguator settled on.
    analyser = Analyzer()
    solutions_cache: dict[str, list] = {}
    out: dict[str, dict] = {}
    total = analysed = 0
    started = time.time()

    for n, record in enumerate(records, 1):
        _, tokens = tokenise(record["textRaw"], strip)
        if not tokens:
            continue
        bound = (bindings.get(record["id"]) or {}).get("tokens") or []
        by_index = {t["i"]: t for t in bound}
        forms = [
            (by_index.get(i, {}).get("surface") or t["raw"])
            for i, t in enumerate(tokens)
        ]
        try:
            results = disambiguator.disambiguate(forms)
        except Exception:
            continue
        for i, result in enumerate(results):
            total += 1
            if not getattr(result, "analyzed", False) or not result.root:
                continue
            analysed += 1
            out[f"{record['id']}:{i}"] = {
                "root": result.root,
                "lemma": result.lemma,
                **grammar_of(result, analyser, solutions_cache),
            }
        if n % 400 == 0:
            print(f"  {n:,}/{len(records):,}  ({time.time()-started:.0f}s)", file=sys.stderr)

    target = OUT / args.corpus / "disambiguated.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")

    print(f"tokens            {total:>9,}")
    print(f"  analysed        {analysed:>9,}  ({100*analysed/max(total,1):.1f}%)")
    print(f"  {time.time()-started:.0f}s")
    print(f"\nwrote {target.relative_to(ROOT.parent)} ({target.stat().st_size/1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
