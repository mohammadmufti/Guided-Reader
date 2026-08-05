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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", default="tajrid")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    records_path = OUT / args.corpus / "records.json"
    if not records_path.exists():
        print(f"no records at {records_path}; run segment.py first", file=sys.stderr)
        return 1

    try:
        from farahidi import Disambiguator
    except ImportError:
        print("farahidi is not installed — pip install farahidi", file=sys.stderr)
        return 1

    records = json.loads(records_path.read_text(encoding="utf-8"))["records"]
    if args.limit:
        records = records[: args.limit]

    strip = inline_strip_patterns(load_config(args.corpus))
    disambiguator = Disambiguator()
    out: dict[str, dict] = {}
    total = analysed = 0
    started = time.time()

    for n, record in enumerate(records, 1):
        _, tokens = tokenise(record["textRaw"], strip)
        if not tokens:
            continue
        try:
            results = disambiguator.disambiguate([t["raw"] for t in tokens])
        except Exception:
            continue
        for i, result in enumerate(results):
            total += 1
            if not getattr(result, "analyzed", False) or not result.root:
                continue
            analysed += 1
            out[f"{record['id']}:{i}"] = {"root": result.root, "lemma": result.lemma}
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
