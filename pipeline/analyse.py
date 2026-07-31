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
from normalise import normalise, root_key  # noqa: E402


def build_analyser():
    import re

    import arramooz.arabicdictionary as ad
    import qalsadi.lemmatizer as ql

    lemmatiser = ql.Lemmatizer()
    # Verbs and nouns are separate tables. Query both, union the ROWS —
    # keeping each row's vocalised lemma, because that is what disambiguates
    # homographs (مُصِرٌّ is صرر; مِصْرٌ is مصر).
    dictionaries = [ad.ArabicDictionary(t) for t in ("verbs", "nouns")]
    rows_cache: dict[str, list[tuple[str, str]]] = {}

    def rows_for(lemma: str) -> list[tuple[str, str]]:
        """(vocalised_lemma, root) pairs, deterministic order."""
        if lemma in rows_cache:
            return rows_cache[lemma]
        found: set[tuple[str, str]] = set()
        for d in dictionaries:
            try:
                for row in d.lookup(lemma) or []:
                    r = dict(row)
                    if r.get("root"):
                        found.add((str(r.get("vocalized") or ""), str(r["root"])))
            except Exception:
                continue
        rows_cache[lemma] = sorted(found)
        return rows_cache[lemma]

    # Lane, as adjudicator: which candidate roots exist as entries at all.
    # (Headword-level matching was tried and adds nothing over existence for
    # this purpose: the fake candidates — خصب for خطاب — are real roots too;
    # what kills them is losing the vocalisation and majority rounds. Lane
    # existence only breaks the residual ties.)
    lane_roots: set[str] = set()
    lane_path = OUT.parent / "lane" / "entries.json"
    if lane_path.exists():
        lane_roots = {root_key(k) for k in json.loads(
            lane_path.read_text(encoding="utf-8"))}

    MARKS = "\u064B-\u0652\u0670"
    _groups = re.compile(rf"([^\s{MARKS}])([{MARKS}]*)")

    def letters_marks(s: str) -> list[tuple[str, str]]:
        return _groups.findall(s)

    def compatible(form: str, voc_lemma: str) -> bool:
        """
        Does the form's own vocalisation admit this dictionary row?

        The lemma's letter skeleton must appear contiguously inside the
        form's (prefixes like وَ/الْ and suffixes sit outside it), and on the
        shared letters every mark BOTH sides wrote must agree — a mark only
        one side wrote is not evidence either way, since neither source
        vocalises exhaustively. Shadda is compared strictly; the final shared
        letter's short vowels are ignored, because there the lemma carries a
        citation case and the form carries a contextual one.
        """
        gf, gl = letters_marks(form), letters_marks(voc_lemma)
        if not gf or not gl:
            return True
        skel_f = [g[0] for g in gf]
        skel_l = [g[0] for g in gl]
        n, m = len(skel_f), len(skel_l)
        for off in range(n - m + 1):
            if skel_f[off:off + m] != skel_l:
                continue
            ok = True
            for j in range(m):
                mf = set(gf[off + j][1])
                ml = set(gl[j][1])
                last = j == m - 1
                if ("\u0651" in mf) != ("\u0651" in ml):  # shadda differs
                    ok = False
                    break
                if last:
                    continue  # citation vs contextual case ending
                shared = (mf - {"\u0651"}) and (ml - {"\u0651"})
                if shared and (mf - {"\u0651"}) != (ml - {"\u0651"}):
                    ok = False
                    break
            if ok:
                return True
        return False

    def choose_root(form: str, lemma: str):
        """
        -> (root, alternatives, basis). The old code took sorted(roots)[0] —
        the ARABIC ALPHABET as tiebreak — which is how خطاب shipped as خصب
        and مصر as صرر. Rounds, each narrowing the last:

          vocalised  rows whose vocalised lemma the form's own marks admit
          majority   the root more dictionary rows vote for
          lane       a candidate that is a real Lane entry beats one that isn't
          unresolved deterministic, and SAID to be arbitrary
        """
        rows = rows_for(lemma)
        if not rows:
            return None, [], None
        all_roots = sorted({r for _, r in rows})
        if len(all_roots) == 1:
            return all_roots[0], [], "unanimous"

        pool = [(v, r) for v, r in rows if compatible(form, v)] or rows
        basis = "vocalised" if len(pool) < len(rows) else None
        tally: dict[str, int] = {}
        for _, r in pool:
            tally[r] = tally.get(r, 0) + 1
        best = max(tally.values())
        leaders = sorted(r for r, c in tally.items() if c == best)
        if len(leaders) == 1:
            winner = leaders[0]
            basis = basis or "majority"
        else:
            in_lane = [r for r in leaders if root_key(r) in lane_roots]
            if len(in_lane) == 1:
                winner, basis = in_lane[0], "lane"
            else:
                winner, basis = leaders[0], "unresolved"
        return winner, [r for r in all_roots if r != winner], basis

    def analyse(form: str) -> dict | None:
        try:
            got = lemmatiser.lemmatize(form, return_pos=True)
        except Exception:
            return None
        if not got or not got[0]:
            return None
        lemma, pos = str(got[0]), (str(got[1]) if len(got) > 1 else None)
        root, alternatives, basis = choose_root(form, lemma)
        return {
            "lemma": lemma,
            "pos": pos if pos not in ("all", "") else None,
            "root": root,
            "rootAlternatives": alternatives,
            "rootBasis": basis,
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

    # Also analyse forms the WITNESS attests that the workbook lacks.
    #
    # The workbook's inventory is bounded by what this corpus happened to
    # produce, so it holds طَائِفَةً and طَائِفَةٍ but not طَائِفَةٌ, and
    # أَصْبَحْتُ but not أَصْبَحْتَ. When the aligner meets the missing reading it
    # has nowhere to bind it and the token falls back to a wrong single option —
    # which is the الْأَعْمَالِ failure exactly. 1,031 tokens are in that position.
    #
    # Restricted to keys the workbook already knows, so this widens the READINGS
    # of known words rather than importing Bukhari's isnad vocabulary wholesale.
    witness = CACHE / "sahih_bukhari_vocalised.csv"
    if witness.exists():
        keys = {normalise(f) for f in forms}
        seen = set(forms)
        import csv

        with witness.open(encoding="utf-8", newline="") as fh:
            for row in csv.reader(fh):
                for cell in row[:1]:
                    for tok in cell.split():
                        tok = tok.strip("()[]{}«».,،؛:؟!\"'")
                        if not tok or tok in seen:
                            continue
                        if normalise(tok) in keys:
                            seen.add(tok)
                            forms.append(tok)
        print(f"  workbook forms + witness readings: {len(forms):,}", file=sys.stderr)

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
