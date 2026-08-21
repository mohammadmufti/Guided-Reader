#!/usr/bin/env python3
"""
Held-out accuracy of the grammar fields, against the edition's own vowelling.

    python pipeline/eval_grammar.py --corpus riyad

WHY THIS CAN BE MEASURED AT ALL. Riyad al-Salihin now ships al-Fahl's printed
harakat, and a printed case vowel IS the i`rab. So the analyser's `case_or_mood`
can be scored against evidence it never saw: the editor's own mark on the last
consonant. No hand-annotation, no sample of 200 — the whole corpus is the test
set, and the gold came from a scholar rather than from us.

WHAT THIS DOES NOT MEASURE. The derivational tags — اسم فاعل, جامد/مشتق,
لازم/متعد — leave no trace in the vowelling and are NOT scored here. Do not read
a good i`rab number as licence to display those. They need their own evidence.

FOUR PLACES THE NAIVE GOLD IS WRONG, each of which cost accuracy until it was
handled. They are grammar, not corner cases, and a reader of this file should
know them:

  * A PAST-TENSE VERB IS MABNI on fatha. Scoring it as mansub measures our own
    gold. Only the imperfect is declined. (72.6% -> 88.3% for verbs.)
  * SUKUN IS NOT A CASE on a noun. It marks waqf or an indeclinable form.
  * THE FIVE VERBS (al-af`al al-khamsa) are marfu` by RETAINING THE NUN, and
    that nun carries fatha. Read as a case vowel it says mansub, and يُخَالِفُونَ
    scores wrong while being right. (169 false errors in a 400-record slice.)
  * A DUAL OR SOUND PLURAL marks case on its suffix, not on the last letter.

Particles are excluded throughout: they are mabni and have no i`rab to check.
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from corpus import inline_strip_patterns, load_config  # noqa: E402
from tokenise import tokenise  # noqa: E402

TANWIN = {"\u064c": "مرفوع", "\u064b": "منصوب", "\u064d": "مجرور"}
SHORT = {"\u064f": "مرفوع", "\u064e": "منصوب",
         "\u0650": "مجرور", "\u0652": "مجزوم"}
NUN = "\u0646"
FIVE = re.compile(r"(ون|ان|ين)$")


def bare(text: str) -> str:
    return "".join(c for c in text if not unicodedata.category(c).startswith("M"))


def printed_case(token: str) -> tuple[str | None, str | None]:
    """
    The mark on the last consonant, and that consonant.

    THE ALIF OF TANWIN FATH IS NOT THE LAST CONSONANT. Accusative tanwin is
    written on the letter BEFORE a final alif — كِتَابًا — so reading marks from
    the end of the string finds nothing and the whole class of mansub nouns
    drops silently out of the sample. A bare final alif or alif maqsura is
    skipped first.
    """
    i = len(token) - 1
    if token and token[-1] in ("\u0627", "\u0649"):
        i -= 1
    marks = []
    while i >= 0 and unicodedata.category(token[i]).startswith("M"):
        marks.append(token[i])
        i -= 1
    if i < 0:
        return None, None
    for mark in marks:
        if mark in TANWIN:
            return TANWIN[mark], token[i]
        if mark in SHORT:
            return SHORT[mark], token[i]
    return None, None


def gold_for(token: str, tags: set[str]) -> tuple[str | None, str]:
    """The i`rab the edition printed, or None where it cannot be read off."""
    stripped = bare(token)
    if "فعل" in tags:
        if "مضارع" not in tags:
            return None, ""          # past and imperative are mabni
        if FIVE.search(stripped):
            return "مرفوع", "verb: al-af`al al-khamsa"
        case, _ = printed_case(token)
        if case in (None, "مجرور"):
            return None, ""          # a verb is never majrur
        return case, "verb (mudari`)"
    if "اسم" in tags:
        case, last = printed_case(token)
        if case is None or case == "مجزوم":
            return None, ""          # sukun is not a case on a noun
        if {"مثنى", "جمع"} & tags and last == NUN:
            return None, ""          # marked on the suffix, not the last letter
        return case, "noun"
    return None, ""                  # particles are mabni


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", default="riyad")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    base = ROOT / "build" / args.corpus
    grammar_path = base / "disambiguated.json"
    records_path = base / "records.json"
    for path in (grammar_path, records_path):
        if not path.exists():
            print(f"missing {path}", file=sys.stderr)
            return 1
    grammar = json.loads(grammar_path.read_text(encoding="utf-8"))
    records = json.loads(records_path.read_text(encoding="utf-8"))
    records = records["records"] if isinstance(records, dict) else records
    if args.limit:
        records = records[: args.limit]
    strip = inline_strip_patterns(load_config(args.corpus))

    scored = collections.defaultdict(collections.Counter)
    confusion = collections.Counter()
    predicted = checkable = 0

    for record in records:
        _, tokens = tokenise(record["textRaw"], strip)
        for i, token in enumerate(tokens):
            found = grammar.get(f"{record['id']}:{i}")
            if not found or "case_or_mood" not in found:
                continue
            predicted += 1
            tags = set(found.get("tags") or [])
            gold, kind = gold_for(token["raw"], tags)
            if gold is None:
                continue
            checkable += 1
            correct = found["case_or_mood"] == gold
            scored[kind][correct] += 1
            if not correct:
                confusion[(kind, found["case_or_mood"], gold)] += 1

    print(f"tokens with a predicted i`rab   {predicted:,}")
    print(f"  of those, checkable against")
    print(f"  the printed vowelling         {checkable:,}\n")
    right = total = 0
    for kind, counts in sorted(scored.items()):
        n = counts[True] + counts[False]
        right += counts[True]
        total += n
        print(f"  {kind:26} n={n:6,}   accuracy {counts[True]/n:6.1%}")
    if total:
        print(f"  {'ALL':26} n={total:6,}   accuracy {right/total:6.1%}")
    print("\n  top confusions (said -> printed):")
    for (kind, said, gold), n in confusion.most_common(8):
        print(f"    {kind:24} {said:8} -> {gold:8}  {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
