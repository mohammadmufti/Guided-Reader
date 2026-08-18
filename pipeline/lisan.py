#!/usr/bin/env python3
"""
Ingest Ibn Manẓūr's *Lisān al-ʿArab* into structured entries, keyed by root.

    python pipeline/fetch.py --corpus lisan
    python pipeline/lisan.py            # mARkdown -> build/lisan/entries.json

WHY THIS EXISTS. Lane's Lexicon answers in English and stops at 5,078 roots.
This answers in Arabic across 8,974, and it is the book Lane cites as `L`. A
student who has spent a month reading `(L)` in Lane's brackets can now open it.

It is deliberately the SAME SHAPE as `lane.py`'s output — root -> entries ->
senses -> runs — so `build.py` links it with the candidate ladder already
written rather than a second one, and the panel renders it with the same
component. Everything below is about the three places this source differs from
Lane, because those are the only places judgement was required.

ONE ARTICLE PER ROOT, NOT PER HEADWORD. Lane files صَلَاةٌ as its own entry
(n24821) under صلو, which is what lets a word be shown ITS OWN entry. Ibn Manẓūr
writes one continuous article per root. So there is no per-headword id to match
and no `laneEntry` analogue: a word resolves to its root's article or to
nothing. The panel must therefore say "the article on the root" and never "this
word's own entry" — claiming the latter would be false for every word here.

`#` LINES ARE NOT PARAGRAPHS. This is the finding that shaped the parser.
Measured across the whole book, 52.5% of `#` units are under 60 characters and
55.5% do not end in terminal punctuation: Shamela breaks lines around block
quotations and verse, mid-sentence. Rendered as-is the ṣalāh article opens

    [1] الصلاة: الركوع والسجود. فأما
    [2] قوله، صلى الله عليه وسلم: لا صلاة لجار المسجد إلا في المسجد
    [3] ، فإنه أراد لا صلاة فاضلة أو كاملة، والجمع صلوات

— one sentence in three pieces, the third starting with a comma. So the article
is REJOINED into continuous prose and then split on sentence enders, which
recovers `الصلاة: الركوع والسجود.` as the opening unit. That is the classical
definition, arriving first, with no ranking heuristic and no sampling.

The units are labelled `level: "sentence"` and carry no label, because Ibn
Manẓūr wrote no sense numbers. Inventing them would be the sampling error this
project already paid for once — see ROADMAP principle 2.

NO HARAKAT, AND NONE INVENTED. Every OpenITI version of this text is fully
undiacritised; all six were checked (JK, ShamAY, Shamela, Shia for Lisān, plus
the Nihāya set) and every one has exactly zero marks. Running a diacritiser over
the entry text is refused on the grounds DIACRITISATION.md §4 already settled:
wrong vowels shown confidently are worse than none. The panel says the text is
unvocalised; that is the whole mitigation and it is the correct one.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "build" / "lisan"

sys.path.insert(0, str(ROOT))
from corpus import ConfigError, load_config, source_path  # noqa: E402
from normalise import root_key, root_variants  # noqa: E402

# The final-weak axis, extended for THIS SOURCE ONLY.
#
# Ibn Manẓūr files final-weak roots under a bare alif — صلا, not صلو or صلى.
# 390 of the book's three-letter heads end in ا. `root_variants()` treats the
# weak axis as ي/ى/و, so without this every final-weak root in every corpus
# misses its article and the reader is shown a section with nothing in it —
# the exact failure `normalise.py` documents for Lane's own spellings.
#
# Measured: coverage of al-Tajrid's rooted forms rises 89.0% -> 96.5%.
#
# WHY NOT JUST ADD ا TO `root_variants()`. Because Lane holds 213 alif-final
# roots of its own, so widening the shared function would move live Lane
# resolution and silently re-point entries that are currently correct. A
# dictionary's filing convention is a property of that dictionary. If Lane
# should gain the same variant, that is its own change with its own held-out
# measurement — not a side effect of adding a second book.
WEAK = ("\u064a", "\u0649", "\u0648", "\u0627")  # ي ى و ا


def lisan_root_variants(root: str) -> list[str]:
    """`root_variants()` plus the bare-alif spelling of a final-weak root."""
    out = list(root_variants(root))
    for v in list(out):
        if v and v[-1] in WEAK:
            for w in WEAK:
                cand = v[:-1] + w
                if cand not in out:
                    out.append(cand)
    return out

# Sentence enders. The Arabic comma and semicolon are NOT here: Ibn Manẓūr
# strings clauses with و and ؛ for pages at a time, and splitting on them
# produces the same fragments the rejoin exists to repair.
SENTENCE_END = re.compile(r"(?<=[.؟!])\s+")

# A unit shorter than this is almost always a stranded quotation fragment
# rather than a sense, and is merged forward into the next one.
MIN_UNIT_CHARS = 25


def compile_strip(cfg: dict) -> list[tuple[str, re.Pattern[str]]]:
    """The strip patterns, in the order the config lists them.

    Order is load-bearing and the config says so: manuscript markers nest
    inside div tags and page brackets, so the nesting marker goes first.
    """
    seg = cfg.get("segmentation") or {}
    out = []
    for spec in seg.get("strip") or []:
        out.append((spec["name"], re.compile(spec["pattern"])))
    return out


def parse(text: str, cfg: dict) -> tuple[dict[str, dict], dict]:
    """
    mARkdown -> {root_key: entry}, plus a counters dict for the report.

    Page and volume are carried from the last `PageV{v}P{p}` seen BEFORE each
    entry head. Those markers sit on their own lines, outside the `#`/`~~` body
    grammar, so they are provenance the body parse would otherwise discard.
    They are worth keeping precisely here: the OpenITI annotator collated this
    digitisation's pagination against the printed Dār Ṣādir edition, so a
    reader can check us against a physical book.
    """
    seg = cfg["segmentation"]
    entry_re = re.compile(seg["entry"])
    para_re = re.compile(seg["paragraph"])
    cont_re = re.compile(seg["continuation"])
    page_re = re.compile(seg["page_marker_alt"])
    strips = compile_strip(cfg)

    counts = {"heads": 0, "unparsed": 0, "with_page": 0, "merged_fragments": 0}

    def clean(s: str) -> str:
        for _, pat in strips:
            s = pat.sub(" ", s)
        return re.sub(r"\s+", " ", s).strip()

    body = text.split("#META#Header#End#", 1)[-1]

    roots: dict[str, dict] = {}
    cur: dict | None = None
    lines: list[str] = []
    last_page: tuple[int, int] | None = None

    def close() -> None:
        """Rejoin, sentence-split, and file the article under way."""
        nonlocal cur, lines
        if cur is None:
            return
        joined = clean(" ".join(lines))
        units: list[str] = []
        for part in SENTENCE_END.split(joined):
            part = part.strip()
            if not part:
                continue
            # Merge a stranded fragment forward rather than shipping it alone.
            if units and len(part) < MIN_UNIT_CHARS:
                units[-1] = f"{units[-1]} {part}"
                counts["merged_fragments"] += 1
            else:
                units.append(part)
        if units:
            key = cur["key"]
            senses = [
                {"label": None, "level": "sentence", "runs": [{"t": "ar", "v": u}]}
                for u in units
            ]
            existing = roots.get(key)
            if existing is None:
                roots[key] = {
                    "root": key,
                    "headword": cur["headword"],
                    "vol": cur["vol"],
                    "page": cur["page"],
                    "entries": [
                        {
                            "nodeid": key,
                            "headword": cur["headword"],
                            "itypes": None,
                            "senses": senses,
                        }
                    ],
                }
            else:
                # 178 of 9,152 heads fold onto a root another head already
                # holds — the book files a few articles twice, and root_key
                # folds a few spelling variants together. Append rather than
                # overwrite: dropping one would silently lose an article.
                existing["entries"][0]["senses"].extend(senses)
        cur, lines = None, []

    for line in body.split("\n"):
        page = page_re.search(line)
        if page:
            last_page = (int(page.group(1)), int(page.group(2)))

        head = entry_re.match(line)
        if head:
            close()
            counts["heads"] += 1
            written = head.group(1).strip()
            key = root_key(written)
            if not key:
                counts["unparsed"] += 1
                continue
            if last_page:
                counts["with_page"] += 1
            cur = {
                "key": key,
                "headword": written,
                "vol": last_page[0] if last_page else None,
                "page": last_page[1] if last_page else None,
            }
            lines = [head.group(2)]
            continue

        if line.startswith("###"):
            # A structural heading — حرف الهمزة, فصل الباء. Ends the article
            # under way and contributes nothing: it is navigation in a book we
            # are not making navigable, only lookupable.
            close()
            continue

        if cur is None:
            continue
        m = para_re.match(line) or cont_re.match(line)
        if m:
            lines.append(m.group(1))

    close()
    return roots, counts


# Anything that survives into a rendered run means the strip config is wrong and
# everything downstream is built on garbage. ADDENDUM-adding-sources.md calls
# this "the single most useful signal that a config is right", and it is checked
# here rather than trusted.
RESIDUAL = re.compile(r"###|~~|PageV\d|<div|\bms\d{3,}\b|\[\s*ص\s*:")


def audit(roots: dict[str, dict]) -> list[str]:
    problems = []
    hits = [
        (r, run["v"][:60])
        for r, payload in roots.items()
        for e in payload["entries"]
        for s in e["senses"]
        for run in s["runs"]
        if RESIDUAL.search(run["v"])
    ]
    if hits:
        problems.append(
            f"{len(hits)} runs carry residual markers, e.g. {hits[0][0]}: {hits[0][1]!r}"
        )
    empty = [r for r, p in roots.items() if not p["entries"][0]["senses"]]
    if empty:
        problems.append(f"{len(empty)} roots have no senses, e.g. {empty[:3]}")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", default="lisan")
    ap.add_argument("--roots", default="", help="optional comma-separated root filter")
    ap.add_argument("--no-assert", action="store_true",
                    help="report the figures without checking them against the config")
    args = ap.parse_args()

    try:
        cfg = load_config(args.corpus)
        path = source_path(cfg, "text")
    except ConfigError as e:
        print(e, file=sys.stderr)
        return 1

    text = path.read_text(encoding=cfg["sources"]["text"].get("encoding", "utf-8"))
    roots, counts = parse(text, cfg)

    wanted = {root_key(r) for r in args.roots.split(",") if r}
    if wanted:
        roots = {k: v for k, v in roots.items() if k in wanted}

    problems = audit(roots)

    n_senses = sum(len(e["senses"]) for p in roots.values() for e in p["entries"])
    chars = sum(len(run["v"]) for p in roots.values() for e in p["entries"]
                for s in e["senses"] for run in s["runs"])
    page_share = counts["with_page"] / max(counts["heads"], 1)

    print(f"entry heads       {counts['heads']:>8,}")
    print(f"unique roots      {len(roots):>8,}")
    print(f"sentence units    {n_senses:>8,}   ({n_senses/max(len(roots),1):.1f} per root)")
    print(f"fragments merged  {counts['merged_fragments']:>8,}")
    print(f"unparsed heads    {counts['unparsed']:>8,}")
    print(f"with vol/page     {counts['with_page']:>8,}   ({page_share:.1%})")
    print(f"text              {chars/1e6:>8.1f} M chars")
    print(f"residual markers  {'NONE' if not problems else 'PRESENT':>8}")

    expected = cfg.get("expected") or {}
    if not args.no_assert and not wanted:
        if expected.get("entry_heads") not in (None, counts["heads"]):
            problems.append(
                f"entry heads {counts['heads']:,} != expected "
                f"{expected['entry_heads']:,} — the source changed under us"
            )
        if expected.get("unique_roots") not in (None, len(roots)):
            problems.append(
                f"unique roots {len(roots):,} != expected {expected['unique_roots']:,}"
            )
        floor = expected.get("min_page_coverage")
        if floor is not None and page_share < floor:
            problems.append(f"vol/page coverage {page_share:.1%} below floor {floor:.0%}")

    if problems:
        print("\nFAILED:", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        return 1

    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / "entries.json"
    out.write_text(json.dumps(roots, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {out.relative_to(ROOT.parent)}  ({out.stat().st_size/1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
