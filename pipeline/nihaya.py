#!/usr/bin/env python3
"""
Ingest Ibn al-Athīr's *al-Nihāya fī Gharīb al-Ḥadīth wa-l-Athar*.

    python pipeline/fetch.py --corpus nihaya
    python pipeline/nihaya.py            # -> build/nihaya/entries.json

WHY THIS EXISTS, AND WHY IT IS NOT A BADGE. This is a dictionary of the
DIFFICULT words in hadith, which makes it the most specific classical apparatus
available for four hadith corpora. It was specified as a flag — "this word
appears in al-Nihāya" — and the flag was measured and abandoned:

    root has an article                     84.0% of al-Tajrīd's rooted forms
    word's form appears in that article     53.1%
    ... excluding Ibn al-Athīr's quotations 43.9%

with قال, النبي, رسول, قلت, سمعت at the top of every variant, and no
discrimination in any frequency band (74.7% at hapax, 78.4% above 100). The
cause is structural, not a parsing defect: *gharīb* dictionaries are organised
by root and roots are shared. A flag that fires on half the corpus tells a
reader nothing, and on a panel whose value is calibrated confidence a
meaningless badge is worse than none.

So it ships as a third section, and the copy says "Ibn al-Athīr's article on
this root" — never "this word is *gharīb*".

WHAT IT DOES HAVE. Attribution sigla on 40.3% of its 25,631 units: (ه) marks
material from al-Harawī's *Gharībayn*, (س) from Abū Mūsā al-Madīnī's supplement
to it, unmarked is Ibn al-Athīr himself. Those become sense labels, exactly as
`lane.py` preserves Lane's bracketed sigla. A siglum also marks a real
boundary — the start of a new *gharīb* item — so it is a unit boundary as well
as a label.

Everything else is `lisan.py`'s shape, deliberately: `build.py` links it with
the ladder already written and the panel renders it with the same component.

NO HARAKAT, AND NONE INVENTED. Every OpenITI version of this text is fully
undiacritised — JK, Masaha, Shamela and Shia were all checked. See
DIACRITISATION.md §4.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "build" / "nihaya"

sys.path.insert(0, str(ROOT))
from corpus import ConfigError, load_config, source_path  # noqa: E402
from dictionaries import audit, sentences  # noqa: E402
from normalise import root_key  # noqa: E402


def compile_strip(cfg: dict) -> list[re.Pattern[str]]:
    seg = cfg.get("segmentation") or {}
    return [re.compile(s["pattern"]) for s in (seg.get("strip") or [])]


def parse(text: str, cfg: dict) -> tuple[dict[str, dict], dict]:
    seg = cfg["segmentation"]
    entry_re = re.compile(seg["entry"])
    struct_re = re.compile(seg["struct"])
    para_re = re.compile(seg["paragraph"])
    cont_re = re.compile(seg["continuation"])
    page_re = re.compile(seg["page_marker_alt"])
    sig_re = re.compile(cfg["sigla"]["pattern"])
    strips = compile_strip(cfg)

    counts = {"heads": 0, "structural": 0, "damaged_heads": 0,
              "with_page": 0, "merged_fragments": 0, "labelled": 0}

    def clean(s: str) -> str:
        for pat in strips:
            s = pat.sub(" ", s)
        return re.sub(r"\s+", " ", s).strip()

    def split_units(joined: str) -> list[tuple[str | None, str]]:
        """
        Article text -> [(siglum, sentence)].

        A siglum opens a new *gharīb* item, so it is a boundary as well as an
        attribution. The siglum labels the FIRST sentence of its item; the rest
        of that item carries no label, because Ibn al-Athīr did not repeat it.
        """
        # `re.split` on a pattern with groups interleaves them, which is fiddly
        # and easy to get subtly wrong. Scanning the boundaries is clearer.
        out: list[tuple[str | None, str]] = []
        marks = list(sig_re.finditer(joined))
        if not marks:
            items = [(None, joined)]
        else:
            items = []
            if marks[0].start() > 0:
                items.append((None, joined[: marks[0].start()]))
            for i, m in enumerate(marks):
                end = marks[i + 1].start() if i + 1 < len(marks) else len(joined)
                items.append((_norm_siglum(m.group(0)), joined[m.end(): end]))
        for label, chunk in items:
            chunk = chunk.strip()
            if not chunk:
                continue
            sents = sentences(chunk)
            counts["merged_fragments"] += getattr(sentences, "merged", 0)
            for i, sent in enumerate(sents):
                out.append((label if i == 0 else None, sent))
        return out

    body = text.split("#META#Header#End#", 1)[-1]
    roots: dict[str, dict] = {}
    cur: dict | None = None
    lines: list[str] = []
    last_page: tuple[int, int] | None = None

    def close() -> None:
        nonlocal cur, lines
        if cur is None:
            return
        units = split_units(clean(" ".join(lines)))
        if units:
            senses = []
            for label, sent in units:
                if label:
                    counts["labelled"] += 1
                senses.append({
                    "label": label,
                    "level": "sentence",
                    "runs": [{"t": "ar", "v": sent}],
                })
            key = cur["key"]
            existing = roots.get(key)
            if existing is None:
                roots[key] = {
                    "root": key,
                    "headword": cur["headword"],
                    "vol": cur["vol"],
                    "page": cur["page"],
                    "entries": [{
                        "nodeid": key,
                        "headword": cur["headword"],
                        "itypes": None,
                        "senses": senses,
                    }],
                }
            else:
                # A root filed twice, or two spellings folding together. Append
                # rather than overwrite: dropping one loses an article.
                existing["entries"][0]["senses"].extend(senses)
        cur, lines = None, []

    def open_entry(written: str) -> None:
        nonlocal cur, lines
        key = root_key(written)
        if not key:
            counts["damaged_heads"] += 1
            return
        if last_page:
            counts["with_page"] += 1
        cur = {
            "key": key,
            "headword": written,
            "vol": last_page[0] if last_page else None,
            "page": last_page[1] if last_page else None,
        }
        lines = []

    for line in body.split("\n"):
        page = page_re.search(line)
        if page:
            last_page = (int(page.group(1)), int(page.group(2)))

        if line.startswith("###"):
            # STRIP FIRST, THEN MATCH. 57 heads carry a trailing `ms0022`-style
            # marker and would not match the anchored pattern otherwise; those
            # 57 are 15 roots that a match-first parser drops silently.
            head = clean(line[3:]).lstrip("| ").strip()
            # ENTRY PATTERN FIRST, STRUCTURAL SECOND. The reverse order looks
            # more natural and loses two real articles: حرف and فصل are both
            # genuine Arabic roots AND both structural keywords, so `(حرف)`
            # and `(فصل)` match the structural filter. The parenthesised
            # no-space form is the more specific signal, so it wins; the
            # structural filter then only sees what the entry patterns
            # declined, which is exactly what it is for.
            m = entry_re.match(head)
            if m:
                close()
                counts["heads"] += 1
                open_entry(m.group(1))
                continue
            if struct_re.match(head):
                close()
                counts["structural"] += 1
                continue
            # CONVERSION DAMAGE, AND IT DOES NOT CLOSE THE ARTICLE.
            #
            # 184 headings match neither pattern: line breaks that landed
            # inside a heading (`ا. ور`, `بت ر`, `إن ا`) and bare words that
            # look like roots but are not.
            #
            # A bare-root pattern was tried and REMOVED. It accepted 103 such
            # headings and recovered exactly ONE root that the parenthesised
            # pattern missed — while corrupting at least one article outright:
            # `### | صلا` sits in the middle of the صلم article as damage, and
            # the pattern opened a spurious صلا entry that swallowed the rest
            # of صلم's text and then had the real `### | (صلا)` appended to it.
            # A reader looking up "prayer" got a paragraph about cropped ears.
            #
            # Treating these as non-boundaries keeps the text with the article
            # it belongs to. Closing on them would strand it under no root at
            # all; opening on them invents a root the author did not write.
            counts["damaged_heads"] += 1
            continue

        if cur is None:
            continue
        m = para_re.match(line) or cont_re.match(line)
        if m:
            lines.append(m.group(1))

    close()
    return roots, counts


def _norm_siglum(raw: str) -> str:
    """`[ه]` and `(ه)` mean the same thing; show one form."""
    letters = re.findall(r"[هس]", raw)
    return "".join(f"({c})" for c in letters)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", default="nihaya")
    ap.add_argument("--roots", default="")
    ap.add_argument("--no-assert", action="store_true")
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
    sig_share = counts["labelled"] / max(n_senses, 1)
    chars = sum(len(r["v"]) for p in roots.values() for e in p["entries"]
                for s in e["senses"] for r in s["runs"])

    print(f"entry heads       {counts['heads']:>8,}")
    print(f"unique roots      {len(roots):>8,}")
    print(f"sentence units    {n_senses:>8,}   ({n_senses/max(len(roots),1):.1f} per root)")
    print(f"with a siglum     {counts['labelled']:>8,}   ({sig_share:.1%})")
    print(f"structural heads  {counts['structural']:>8,}")
    print(f"damaged heads     {counts['damaged_heads']:>8,}   (kept with their article)")
    print(f"text              {chars/1e6:>8.1f} M chars")
    print(f"residual markers  {'NONE' if not problems else 'PRESENT':>8}")

    expected = cfg.get("expected") or {}
    if not args.no_assert and not wanted:
        if expected.get("entry_heads") not in (None, counts["heads"]):
            problems.append(f"entry heads {counts['heads']:,} != expected {expected['entry_heads']:,}")
        if expected.get("unique_roots") not in (None, len(roots)):
            problems.append(f"unique roots {len(roots):,} != expected {expected['unique_roots']:,}")
        floor = expected.get("min_siglum_share")
        if floor is not None and sig_share < floor:
            problems.append(f"siglum share {sig_share:.1%} below floor {floor:.0%}")

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
