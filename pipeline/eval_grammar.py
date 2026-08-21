#!/usr/bin/env python3
"""
Held-out accuracy of the grammar fields, against the edition's own vowelling.

    python pipeline/eval_grammar.py --corpus riyad

WHY THIS CAN BE MEASURED AT ALL. A printed case vowel IS the i`rab, so
`case_or_mood` can be scored against evidence the analyser never saw. No
hand-annotation, no sample of 200 — the whole corpus is the test set, and the
gold came from a scholar rather than from us.

THE GOLD IS THE BOUND TOKEN, NOT THE SOURCE TEXT. An earlier version of this
file read `records.json`, which is the text as the corpus supplies it. Every
corpus but Riyad reads its text from OpenITI, and OpenITI strips diacritics, so
that version could only ever measure one book — and concluded, wrongly, that no
other test bed existed.

The pipeline VOWELS those texts. `bindings.json` carries a vocalised `surface`
for each token and the tier it came from, and two of those tiers are evidence
independent of Alkhalil:

    tier 0  the source is vowelled          — the edition's own printing
    tier 2  aligned against a vocalised
            witness edition                 — a different editor's printing

Tiers 1, 3 and 4 are NOT usable here. Tier 1 is a type-level reading from the
shared lexicon, and Tiers 3 and 4 are our own heuristics; scoring an analyser
against our guesses measures agreement between two guesses.

On Riyad that is 114,778 tokens rather than the matn of one book.

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

# Tiers whose vowelling is INDEPENDENT of the analyser being scored.
#   0  the source itself is vowelled
#   2  aligned against a vocalised witness edition
# Tier 1 is a type-level reading from the shared lexicon; Tiers 3 and 4 are our
# own heuristics. Scoring against those measures two guesses agreeing.
GOLD_TIERS = {0, 2}
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
    bindings_path = base / "bindings.json"
    for path in (grammar_path, bindings_path):
        if not path.exists():
            print(f"missing {path}", file=sys.stderr)
            return 1
    grammar = json.loads(grammar_path.read_text(encoding="utf-8"))
    bindings = json.loads(bindings_path.read_text(encoding="utf-8"))

    scored = collections.defaultdict(collections.Counter)
    confusion = collections.Counter()
    tiers_seen = collections.Counter()
    predicted = checkable = 0

    for n, (record_id, record) in enumerate(bindings.items()):
        if args.limit and n >= args.limit:
            break
        for token in record["tokens"]:
            found = grammar.get(f"{record_id}:{token['i']}")
            if not found or "case_or_mood" not in found:
                continue
            predicted += 1
            if token.get("tier") not in GOLD_TIERS:
                continue
            tags = set(found.get("tags") or [])
            gold, kind = gold_for(token["surface"], tags)
            if gold is None:
                continue
            checkable += 1
            tiers_seen[token["tier"]] += 1
            correct = found["case_or_mood"] == gold
            scored[kind][correct] += 1
            if not correct:
                confusion[(kind, found["case_or_mood"], gold)] += 1

    print(f"tokens with a predicted i`rab   {predicted:,}")
    print(f"  vowelled at tier 0 or 2       "
          f"{sum(tiers_seen.values()):,}  " +
          "  ".join(f"tier {t}: {n:,}" for t, n in sorted(tiers_seen.items())))
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
