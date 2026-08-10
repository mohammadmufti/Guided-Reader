#!/usr/bin/env python3
"""
Export the workbook's LEXICOGRAPHY into a corpus-independent store.

    python pipeline/glossary.py --workbook <xlsx>   # -> build/glossary/glossary.json

WHY. The workbook was never meant to be permanent, and most of what it does
turns out not to need it:

    inventory of readings   derivable  -- `Lexicon.seed_from_witness`
    freq / rank / pct       derivable  -- counts over the corpus
    doc_freq / layers       derivable  -- same
    lemma / root / POS      derivable  -- `analyse.py`
    gloss, divergence,      NOT derivable
    technical senses,
    curated names, review

Measured: al-Tajrid with the workbook removed but the witness read as a type
lexicon reaches 96.6% Tier 1+2 against the workbook path's 97.2% -- 0.6 points
-- and unbound falls to 0.3%. So the workbook's structural contribution is
almost nothing. What it holds that nothing else does is MEANING: 21,028 glosses
and the divergence analysis, which are scholarship rather than computation.

So the migration is not "drop the workbook", it is "stop treating the workbook
as a pipeline INPUT and treat it as a one-time SOURCE". This script runs once,
lifts the lexicography out, and after that the xlsx can sit in an archive.

The store is keyed by `match_id` -- `stable_id(search_key, vocalized)`, derived
from the form and never from frequency -- so an entry is corpus-independent by
construction. That is what already lets al-Tajrid's glosses serve the Muwatta',
and it is why this file is a glossary rather than a copy of one book's workbook.

WHAT IS DELIBERATELY NOT COPIED. Anything measured over al-Tajrid: freq, rank,
pct, cum_pct, doc_freq, layers, first_record, kwic. Those describe one text.
Carrying them into a shared store would let one book's statistics rank another
book's candidates, which is the contamination the corpus isolation work exists
to prevent.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "build" / "glossary"

# Lexicography: true of the WORD, wherever it occurs.
CARRY = (
    "gloss_msa", "lemma", "lemmaVocalised", "glossCamel", "segments", "root", "pos", "unvocalized",
    "divergence", "technical_sense", "domain", "literal_sense",
    "classical_keywords", "lane_root", "morph_confidence", "pos_agreement",
    "din_31635", "lemma_din",
)

# Statistics: true of the word IN AL-TAJRID. Never carried.
REFUSE = (
    "freq", "rank", "pct", "cum_pct", "doc_freq", "layers",
    "first_record", "kwic", "classical_sense_sample", "overlap_score",
)


def build(workbook: Path) -> dict:
    sys.path.insert(0, str(ROOT))
    from lexicon import stable_id

    # Through the adapter: this script is the one-time lift, and it should
    # not be a second place that knows the spreadsheet's shape.
    import workbook as workbook_adapter
    entries: dict[str, dict] = {}
    for row in workbook_adapter.read_lexicography(workbook):
        key, voc = str(row["search_key"]), str(row["vocalized"])
        if not key or not voc or voc == "nan":
            continue
        mid = stable_id(key, voc)
        e = {"match_id": mid, "search_key": key, "vocalized": voc}
        for field in CARRY:
            val = row.get(field)
            if val is None or str(val) in ("nan", ""):
                continue
            e[field] = str(val)
        entries[mid] = e
    return entries


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workbook", required=True)
    ap.add_argument("--label", default="tajrid-workbook",
                    help="recorded on every entry as `glossFrom`")
    args = ap.parse_args()

    path = Path(args.workbook)
    if not path.exists():
        print(f"no workbook at {path}", file=sys.stderr)
        return 1

    entries = build(path)
    OUT.mkdir(parents=True, exist_ok=True)
    doc = {"source": args.label, "entries": entries}
    (OUT / "glossary.json").write_text(json.dumps(doc, ensure_ascii=False),
                                       encoding="utf-8")

    glossed = sum(1 for e in entries.values() if e.get("gloss_msa"))
    rooted = sum(1 for e in entries.values() if e.get("root"))
    print(f"wrote {OUT / 'glossary.json'}")
    print(f"  {len(entries):,} entries")
    print(f"  {glossed:,} with a gloss ({100*glossed/len(entries):.1f}%)")
    print(f"  {rooted:,} with a root  ({100*rooted/len(entries):.1f}%)")
    print(f"  corpus statistics deliberately NOT carried: {', '.join(REFUSE[:6])}…")
    return 0


if __name__ == "__main__":
    sys.exit(main())
