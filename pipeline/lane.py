#!/usr/bin/env python3
"""
Ingest Lane's *Arabic-English Lexicon* into structured entries. Roadmap A.2.

    python pipeline/lane.py            # sqlite -> build/lane/entries.json

WHY THIS EXISTS. v1 shipped one *sampled* sense per root, taken from the supplied
workbook, and it was frequently the wrong one — the sample for صلو reads "the
middle of the back of a human being", which is a real sense of the root and
useless as a gloss for salah. Measured across the shipped payload, the mean full
entry holds 15.8 senses and we were showing one, chosen mechanically. So roughly
94% of the classical material was discarded upstream, irreversibly.

The fix is not a better sample. It is to carry the whole entry and let the
presentation layer make selection visible as a choice.

WHAT THIS GIVES US THAT SAMPLING COULD NOT. Lane is organised as roots
containing per-headword entries: صَلَاةٌ is its own entry (n24821) under root
صلو, and it opens "Prayer, supplication, or petition: (S, M, Msb, K:) this is
said to be its primary signification". So instead of a sense sampled from
anywhere in the root, a word can be shown ITS OWN ENTRY. That is a different
kind of answer.

STRUCTURE. The XML is TEI-ish with a small, regular tag set:
  entryFree  the entry, keyed by headword
  sense      numbered senses — the structure that makes real rendering possible
  foreign    Arabic runs, lang="ar"
  hi         emphasis, rend="ital"
  orth       orthographic variants of the headword
  ref        cross-references to other entries
  tropical / assumedtropical   Lane's figurative-usage markers
  pb         page breaks in the printed edition

Inline content is flattened to a list of runs so the client renders it without
an HTML parser and without any possibility of injecting markup.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache"
OUT = ROOT / "build" / "lane"

# Lane's source sigla, expanded. Keeping them is provenance, not clutter — a
# student who learns to read them gains something — but they are opaque unless
# the interface can expand them.
SIGLA = {
    "K": "al-Qāmūs al-Muḥīṭ",
    "S": "al-Ṣiḥāḥ (al-Jawharī)",
    "M": "al-Muḥkam (Ibn Sīda)",
    "Msb": "al-Miṣbāḥ al-Munīr",
    "TA": "Tāj al-ʿArūs",
    "Mgh": "al-Mughrib",
    "MF": "Murtaḍā al-Zabīdī's commentary",
    "L": "Lisān al-ʿArab",
    "JK": "Jāmiʿ al-Kalām",
    "IAar": "Ibn al-Aʿrābī",
    "AA": "Abū ʿAmr",
    "As": "al-Aṣmaʿī",
    "Lh": "al-Liḥyānī",
    "IB": "Ibn Barrī",
    "ISd": "Ibn Sīda",
    "Az": "al-Azharī",
    "A": "Asās al-Balāgha",
}

RUN_TAGS = {
    "foreign": "ar",
    "hi": "i",
    "orth": "ar",
    "ref": "ref",
    "quote": "q",
    "tropical": "trop",
    "assumedtropical": "trop",
}


def parse_entry(xml: str) -> dict | None:
    """
    One `<entryFree>` -> {headword, forms, senses}.

    `<sense>` is NOT a container in this XML. It is an inline DIVIDER carrying a
    label — `<sense type="b" n="2">-b2-</sense>` — and the sense it introduces is
    the flow that follows it, up to the next divider. Modelling it as a container
    yields five senses whose entire content is the strings "-b2-" through "-b5-",
    which is what the first version of this function did.

    Lane's labels are two-level: `type="A"` marks a major division, `type="b"` a
    sub-sense. Both are kept, because the hierarchy is how a reader navigates a
    56-sense entry.
    """
    try:
        el = ElementTree.fromstring(xml)
    except ElementTree.ParseError:
        try:
            el = ElementTree.fromstring(re.sub(r"&(?![a-z]+;|#)", "&amp;", xml))
        except ElementTree.ParseError:
            return None

    forms = [
        (o.text or "").strip()
        for f in el.findall("form")
        for o in f.findall("orth")
        if (o.text or "").strip()
    ]
    itypes = [(i.text or "").strip() for f in el.findall("form") for i in f.findall("itype")]

    senses: list[dict] = [{"label": None, "level": "primary", "runs": []}]

    def push(kind: str, value: str) -> None:
        value = re.sub(r"\s+", " ", value)
        if not value.strip():
            runs = senses[-1]["runs"]
            if runs and not runs[-1]["v"].endswith(" "):
                runs[-1]["v"] += " "
            return
        runs = senses[-1]["runs"]
        if runs and runs[-1]["t"] == kind:
            runs[-1]["v"] += value
        else:
            runs.append({"t": kind, "v": value})

    def walk(node: ElementTree.Element, kind: str) -> None:
        if node.text:
            push(kind, node.text)
        for child in node:
            tag = child.tag
            if tag == "sense":
                # A divider: everything after it belongs to a new sense.
                senses.append(
                    {
                        "label": (child.get("type") or "") + (child.get("n") or ""),
                        "level": "major" if child.get("type") == "A" else "sub",
                        "runs": [],
                    }
                )
            elif tag == "form":
                pass  # headword morphology, already captured above
            elif tag == "pb":
                pass  # printed page break: provenance, not content
            elif tag == "ref":
                target = child.get("target")
                if target:
                    push("ref", target)
            else:
                walk(child, RUN_TAGS.get(tag, kind))
            if child.tail:
                push(kind, child.tail)

    walk(el, "t")

    cleaned = []
    for sense in senses:
        runs = [r for r in sense["runs"] if r["v"].strip()]
        for r in runs:
            r["v"] = r["v"].strip() if r is runs[-1] else r["v"]
        if runs:
            sense["runs"] = runs
            cleaned.append(sense)

    return {
        "key": el.get("key") or (forms[0] if forms else None),
        "type": el.get("type"),
        "forms": forms,
        "itypes": [i for i in itypes if i],
        "senses": cleaned,
    }


def chars(entry: dict) -> int:
    return sum(len(r["v"]) for s in entry["senses"] for r in s["runs"])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default=str(CACHE / "lane" / "lexicon.sqlite"))
    ap.add_argument("--roots", default="", help="optional comma-separated root filter")
    args = ap.parse_args()

    db = Path(args.db)
    if not db.exists():
        archive = CACHE / "lane" / "lexicon.sqlite.zip"
        if not archive.exists():
            print(f"missing {db} and {archive}. Run: python pipeline/fetch.py --corpus lane",
                  file=sys.stderr)
            return 1
        db.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive) as z:
            z.extract("lexicon.sqlite", db.parent)

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row

    wanted = {r for r in args.roots.split(",") if r} or None
    roots: dict[str, dict] = {}
    failed = 0
    for row in conn.execute(
        "SELECT root, nodeid, headword, word, bareword, page, nodenum, xml "
        "FROM entry ORDER BY root, nodenum"
    ):
        root = row["root"]
        if wanted and root not in wanted:
            continue
        parsed = parse_entry(row["xml"])
        if parsed is None:
            failed += 1
            continue
        entry = {
            "nodeid": row["nodeid"],
            "headword": row["headword"] or row["word"],
            "bareword": row["bareword"],
            "page": row["page"],
            **parsed,
        }
        entry["chars"] = chars(entry)
        roots.setdefault(root, {"root": root, "entries": []})["entries"].append(entry)

    for row in conn.execute("SELECT word, page FROM root"):
        if row["word"] in roots:
            roots[row["word"]]["page"] = row["page"]

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "entries.json"
    path.write_text(json.dumps(roots, ensure_ascii=False), encoding="utf-8")

    n_entries = sum(len(r["entries"]) for r in roots.values())
    n_senses = sum(len(e["senses"]) for r in roots.values() for e in r["entries"])
    total_chars = sum(e["chars"] for r in roots.values() for e in r["entries"])
    print(f"roots            {len(roots):>8,}")
    print(f"entries          {n_entries:>8,}   ({n_entries/max(len(roots),1):.1f} per root)")
    print(f"numbered senses  {n_senses:>8,}")
    print(f"unparseable xml  {failed:>8,}")
    print(f"text             {total_chars/1e6:>8.1f} M chars")
    print(f"sigla expanded   {len(SIGLA):>8,}")
    print(f"\nwrote {path.relative_to(ROOT.parent)}  ({path.stat().st_size/1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
