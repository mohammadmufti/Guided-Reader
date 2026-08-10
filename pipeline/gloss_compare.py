"""
Where the analyser's gloss and the workbook's disagree.

The reader now shows two glosses: a short modern one from CAMeL's `stemgloss`,
and al-Tajrid's curated one beneath it. They agree most of the time. Where they
do not, one of them is wrong, and this says which pairs to look at.

Run it after a build:

    python pipeline/gloss_compare.py                  # summary + top disagreements
    python pipeline/gloss_compare.py --all            # every disagreement
    python pipeline/gloss_compare.py --out report.md  # write it down

NORMALISE BEFORE COMPARING, or the report is mostly noise. Three conventions
differ without the meanings differing at all:

  * Buckwalter writes a multi-word sense with underscores: `kneeling_down`.
  * The workbook packs alternatives into one string with a slash: `it/he`,
    where the analyser lists them separately as `it`, `he`.
  * Case, punctuation and surrounding brackets vary freely on both sides.

Comparing raw strings called 40% of entries different. After normalising, the
number that genuinely share no sense is far smaller, and those are worth
reading one by one.
"""

from __future__ import annotations

import argparse
import glob
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT.parent / "web" / "public" / "data"


def senses(raw: list[str]) -> set[str]:
    """
    A comparable set of senses.

    Splits on the slash the workbook uses for alternatives, folds underscores
    to spaces, drops bracketed asides and anything that is not a letter or a
    space. What is left is the meaning, in the same shape from both sources.
    """
    out: set[str] = set()
    for s in raw:
        s = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", str(s))
        for part in re.split(r"[/;,]", s.replace("_", " ")):
            t = re.sub(r"[^a-z ]", " ", part.lower())
            t = re.sub(r"\s+", " ", t).strip()
            # `be` and `to` carry no weight: the workbook writes "be frail"
            # where the analyser writes "frail".
            t = re.sub(r"^(to|be|being) ", "", t)
            if t:
                out.add(t)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="tajrid",
                    help="the corpus whose workbook glosses are compared")
    ap.add_argument("--all", action="store_true", help="every disagreement, not the top 40")
    ap.add_argument("--out", type=Path, help="write the report here")
    args = ap.parse_args()

    entries: dict = {}
    shards = sorted(glob.glob(str(DATA / "corpora" / args.corpus / "lex" / "surface-*.json")))
    shards += sorted(glob.glob(str(DATA / "lexicon" / "surface-*.json")))
    if not shards:
        raise SystemExit(f"no payload for {args.corpus!r} — run pipeline/build.py first")
    for f in shards:
        entries.update(json.loads(Path(f).read_text(encoding="utf-8")))

    # Frequencies live in their own shards — the surface entry carries none, so
    # ordering by `freq` there silently sorts everything as zero.
    freq: dict[str, int] = {}
    for f in sorted(glob.glob(str(DATA / "corpora" / args.corpus / "lex" / "stats-*.json"))):
        for mid, row in json.loads(Path(f).read_text(encoding="utf-8")).items():
            freq[mid] = int(row.get("freq") or 0)

    both = [(mid, e) for mid, e in entries.items()
            if e.get("gloss") and e.get("glossQuick")]
    if not both:
        raise SystemExit("no entry carries both glosses — is analyses.json current?")

    same = overlap = 0
    rows: list[tuple[int, str, list[str], list[str]]] = []
    for mid, e in both:
        w, c = senses(e["gloss"]["senses"]), senses(e["glossQuick"]["senses"])
        if w == c:
            same += 1
        elif w & c:
            overlap += 1
        else:
            rows.append((freq.get(mid, 0), str(e.get("vocalized")),
                         e["gloss"]["senses"][:4], e["glossQuick"]["senses"][:4]))
    rows.sort(key=lambda r: (-r[0], r[1]))

    n = len(both)
    L = [
        f"# Glosses compared — {args.corpus}",
        "",
        "The analyser's `stemgloss` against the workbook's curated gloss, after",
        "normalising the conventions that differ without the meaning differing:",
        "underscores, the workbook's `a/b` alternatives, case and brackets.",
        "",
        f"| | entries | share |",
        f"|---|--:|--:|",
        f"| carry both glosses | {n:,} | |",
        f"| identical | {same:,} | {100*same/n:.1f}% |",
        f"| partial overlap | {overlap:,} | {100*overlap/n:.1f}% |",
        f"| **no sense in common** | **{len(rows):,}** | **{100*len(rows)/n:.1f}%** |",
        "",
        "Ordered by how often the word occurs, so the ones that matter come first.",
        "",
        "| word | freq | workbook | analyser |",
        "|---|--:|---|---|",
    ]
    for fq, voc, w, c in (rows if args.all else rows[:40]):
        L.append(f"| {voc} | {fq:,} | {'; '.join(w)} | {'; '.join(c)} |")
    if not args.all and len(rows) > 40:
        L.append("")
        L.append(f"_{len(rows) - 40:,} more; run with `--all`._")

    text = "\n".join(L)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
