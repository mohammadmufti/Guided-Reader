#!/usr/bin/env python3
"""
Run the morphological analysers directly and cache the result.

    python pipeline/analyse.py            # -> build/morphology/analyses.json

WHY. The supplied workbook's own README says its morphology is
`qalsadi` reconciled against Buckwalter/AraMorph. So it is already this output,
cached, filtered through one corpus, and lossy: 409 forms reach us as
`pos=particle` with a one-letter lemma and no root because a reconciliation step
we cannot inspect discarded the stem. Running the analysers ourselves is not
adding an opinion — it is removing an intermediary.

THE CHAIN, and the two dead ends found on the way to it.

    qalsadi.lemmatize(form)  ->  lemma, pos
    arramooz(verbs U nouns)  ->  root, by lemma

`tashaphyne.get_root()` looked like the obvious route and is not: applied to a
surface form it returns the whole word, and applied to a lemma it invents
geminate roots — بعث becomes عثث, بني becomes بنن, خشي becomes خشش. It is a light
stemmer, not a root extractor, and it agreed with the workbook on only 62.4% of
forms. `arramooz` is a real dictionary with a root column and agrees on 92.3%.

BOTH TABLES MUST BE QUERIED. Verbs and nouns are separate dictionaries: بايع
resolves only in verbs, صلاة and بنيان only in nouns. Querying one halves the
coverage silently.

PRECEDENCE. This provider sits BELOW the workbook. Where the workbook has a root,
it keeps it; where it does not, this fills the gap. The two disagree on 4.1% of
forms and neither is authoritative — `حِسَابُكُمَا` is rooted حشر by the workbook
and حسب here, and here is right — so a disagreement is recorded rather than
silently resolved.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache"
OUT = ROOT / "build" / "morphology"

sys.path.insert(0, str(ROOT))
from normalise import root_key  # noqa: E402


def build_analyser():
    import arramooz.arabicdictionary as ad
    import qalsadi.lemmatizer as ql

    lemmatiser = ql.Lemmatizer()
    # Verbs and nouns are separate tables. Query both, union the roots.
    dictionaries = [ad.ArabicDictionary(t) for t in ("verbs", "nouns")]
    root_cache: dict[str, list[str]] = {}

    def roots_for(lemma: str) -> list[str]:
        if lemma in root_cache:
            return root_cache[lemma]
        found: set[str] = set()
        for d in dictionaries:
            try:
                for row in d.lookup(lemma) or []:
                    value = dict(row).get("root")
                    if value:
                        found.add(str(value))
            except Exception:
                continue
        root_cache[lemma] = sorted(found)
        return root_cache[lemma]

    def analyse(form: str) -> dict | None:
        try:
            got = lemmatiser.lemmatize(form, return_pos=True)
        except Exception:
            return None
        if not got or not got[0]:
            return None
        lemma, pos = str(got[0]), (str(got[1]) if len(got) > 1 else None)
        roots = roots_for(lemma)
        return {
            "lemma": lemma,
            "pos": pos if pos not in ("all", "") else None,
            # One root when the dictionaries agree; the alternatives are kept so
            # a disagreement is visible rather than resolved by coin toss.
            "root": roots[0] if roots else None,
            "rootAlternatives": roots[1:] if len(roots) > 1 else [],
        }

    return analyse


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workbook", default=str(CACHE / "Tajrid_frequency_tables.xlsx"))
    ap.add_argument("--limit", type=int, default=0, help="for a quick smoke run")
    args = ap.parse_args()

    import pandas as pd

    path = Path(args.workbook)
    if not path.exists():
        path = ROOT.parent / "Tajrid_frequency_tables.xlsx"
    if not path.exists():
        print(f"no workbook at {args.workbook}", file=sys.stderr)
        return 1

    surface = pd.read_excel(path, sheet_name="Surface")
    forms = [str(v) for v in surface["vocalized"]]
    if args.limit:
        forms = forms[: args.limit]

    analyse = build_analyser()
    out: dict[str, dict] = {}
    for n, form in enumerate(forms, 1):
        if form in out:
            continue
        got = analyse(form)
        if got:
            out[form] = got
        if n % 5000 == 0:
            print(f"  {n:,}/{len(forms):,}", file=sys.stderr)

    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / "analyses.json"
    target.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")

    with_root = sum(1 for v in out.values() if v["root"])
    disputed = sum(1 for v in out.values() if v["rootAlternatives"])
    print(f"analysed        {len(out):,} forms")
    print(f"  with a root   {with_root:,}  ({100*with_root/len(out):.1f}%)")
    print(f"  root disputed {disputed:,}  (dictionaries offer more than one)")
    print(f"\nwrote {target.relative_to(ROOT.parent)} ({target.stat().st_size/1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
